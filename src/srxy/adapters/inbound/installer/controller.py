"""PySide6 controller for the install / uninstall wizard."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, QThread, Signal, Slot

from srxy.adapters.inbound.installer.gpu import has_accelerated_gpu
from srxy.adapters.inbound.installer.help_text import help_text
from srxy.adapters.inbound.installer.install import InstallOptions, install_srxy
from srxy.adapters.inbound.installer.manifest import (
	is_non_empty_foreign_prefix,
	is_srxy_prefix,
	prefix_needs_confirmation,
)
from srxy.adapters.inbound.installer.privacy import privacy_disclaimer_html, privacy_disclaimer_text
from srxy.adapters.inbound.installer.uninstall import discover_default_prefix, uninstall_prefix, uninstall_search_hint
from srxy.application.install_paths import default_install_prefix
from srxy.i18n import tr as translate


def _format_byte_size(num: float) -> str:
	"""Format a byte count for progress UI (KB / MB / GB)."""
	value = max(0.0, float(num))
	units = ("B", "KB", "MB", "GB", "TB")
	size = value
	unit_index = 0
	while size >= 1024.0 and unit_index < len(units) - 1:
		size /= 1024.0
		unit_index += 1
	if unit_index == 0:
		return f"{int(size)} {units[unit_index]}"
	return f"{size:.1f} {units[unit_index]}"


def _emit_progress_safe(signal: object, done: int | float, total: int | float, label: str):
	"""Emit download progress as floats so multi-GB sizes fit Qt's signal types."""
	emit = getattr(signal, "emit", None)
	if callable(emit):
		emit(float(done), float(total), label)


class _Worker(QThread):
	status = Signal(str)
	# Floats: byte totals often exceed signed 32-bit int (Shiboken OverflowError).
	progress = Signal(float, float, str)
	task = Signal(int, int, str)
	finished_ok = Signal()
	failed = Signal(str)

	def __init__(
		self,
		action: str,
		options: InstallOptions | None,
		prefix: Path | None,
		*,
		confirm_unsafe: bool = False,
	):
		super().__init__()
		self._action = action
		self._options = options
		self._prefix = prefix
		self._confirm_unsafe = confirm_unsafe

	def run(self):
		try:
			if self._action == "install":
				if self._options is None:
					raise RuntimeError("install requires options")
				install_srxy(
					self._options,
					status=lambda message: self.status.emit(message),
					progress=lambda done, total, label: _emit_progress_safe(self.progress, done, total, label),
					task=lambda index, total, label: self.task.emit(index, total, label),
				)
			elif self._action == "reinstall":
				if self._options is None or self._prefix is None:
					raise RuntimeError("reinstall requires options and prefix")
				from srxy.adapters.inbound.installer.install import plan_install_phases

				install_phases = plan_install_phases(self._options)
				overall_total = 1 + len(install_phases)
				remove_label = translate("installer.status.removing_app")
				self.status.emit(remove_label)
				self.task.emit(1, overall_total, remove_label)
				_emit_progress_safe(self.progress, 0, 0, remove_label)
				uninstall_prefix(
					self._prefix,
					status=lambda message: self.status.emit(message),
					confirm_unsafe=self._confirm_unsafe,
				)
				_emit_progress_safe(self.progress, 1, 1, remove_label)
				install_srxy(
					self._options,
					status=lambda message: self.status.emit(message),
					progress=lambda done, total, label: _emit_progress_safe(self.progress, done, total, label),
					task=lambda index, total, label: self.task.emit(index, total, label),
					task_offset=1,
					task_total=overall_total,
				)
			elif self._action == "uninstall":
				if self._prefix is None:
					raise RuntimeError("uninstall requires a prefix")
				uninstall_prefix(
					self._prefix,
					status=lambda message: self.status.emit(message),
					confirm_unsafe=self._confirm_unsafe,
				)
			else:
				raise RuntimeError(f"unknown action: {self._action}")
			self.finished_ok.emit()
		except Exception as exc:
			self.failed.emit(str(exc))


class InstallerController(QObject):
	modeChanged = Signal()
	prefixChanged = Signal()
	privacyAckChanged = Signal()
	downloadTesseractChanged = Signal()
	downloadFfmpegChanged = Signal()
	installSemanticChanged = Signal()
	prefetchModelsChanged = Signal()
	addToPathChanged = Signal()
	languageChanged = Signal()
	busyChanged = Signal()
	statusChanged = Signal()
	errorChanged = Signal()
	progressLabelChanged = Signal()
	progressValueChanged = Signal()
	progressDeterminateChanged = Signal()
	overallProgressChanged = Signal()
	taskProgressChanged = Signal()
	pageChanged = Signal()
	finishedChanged = Signal()
	canGoBackChanged = Signal()
	unsafeConfirmChanged = Signal()

	def __init__(self):
		super().__init__()
		self._mode = "install"
		self._prefix = str(default_install_prefix())
		self._privacy_ack = False
		self._download_tesseract = True
		self._download_ffmpeg = True
		self._has_gpu = has_accelerated_gpu()
		# When a usable GPU is present, opt into all AI-related extras by default.
		self._install_semantic = self._has_gpu
		self._prefetch_models = self._has_gpu
		self._add_to_path = True
		from srxy.i18n import get_language, resolve_language, set_language

		set_language(resolve_language())
		self._language = get_language()
		self._busy = False
		self._status = ""
		self._error = ""
		self._progress_label = ""
		self._progress_value = 0.0
		self._progress_determinate = False
		self._overall_index = 0
		self._overall_total = 0
		self._overall_progress_value = 0.0
		self._task_done = 0.0
		self._task_total = 0.0
		self._page = "mode"
		self._finished = False
		self._worker: _Worker | None = None
		self._confirm_unsafe = False
		self._unsafe_confirm_open = False
		self._unsafe_confirm_message = ""
		self._pending_unsafe_action: str | None = None
		discovered = discover_default_prefix()
		if discovered is not None:
			self._uninstall_prefix = str(discovered)
		else:
			self._uninstall_prefix = ""

	def _set_busy(self, value: bool):
		if self._busy != value:
			self._busy = value
			self.busyChanged.emit()
			self.canGoBackChanged.emit()

	@Property(str, notify=modeChanged)
	def mode(self) -> str:
		return self._mode

	@Slot(str)
	def setMode(self, value: str):
		if value not in {"install", "reinstall", "uninstall"}:
			return
		if self._mode != value:
			self._mode = value
			self.modeChanged.emit()
			self.canGoBackChanged.emit()
			if value == "reinstall":
				discovered = discover_default_prefix()
				if discovered is not None:
					self.setPrefix(str(discovered))

	@Property(str, notify=prefixChanged)
	def prefix(self) -> str:
		return self._prefix

	@Slot(str)
	def setPrefix(self, value: str):
		text = value.strip()
		if self._prefix != text:
			self._prefix = text
			self.prefixChanged.emit()

	@Property(str, notify=prefixChanged)
	def uninstallPrefix(self) -> str:
		return self._uninstall_prefix

	@Slot(str)
	def setUninstallPrefix(self, value: str):
		text = value.strip()
		if self._uninstall_prefix != text:
			self._uninstall_prefix = text
			self.prefixChanged.emit()

	@Property(bool, notify=privacyAckChanged)
	def privacyAck(self) -> bool:
		return self._privacy_ack

	@Slot(bool)
	def setPrivacyAck(self, value: bool):
		if self._privacy_ack != value:
			self._privacy_ack = value
			self.privacyAckChanged.emit()

	@Property(bool, notify=downloadTesseractChanged)
	def downloadTesseract(self) -> bool:
		return self._download_tesseract

	@Slot(bool)
	def setDownloadTesseract(self, value: bool):
		if self._download_tesseract != value:
			self._download_tesseract = value
			self.downloadTesseractChanged.emit()

	@Property(bool, notify=downloadFfmpegChanged)
	def downloadFfmpeg(self) -> bool:
		return self._download_ffmpeg

	@Slot(bool)
	def setDownloadFfmpeg(self, value: bool):
		if self._download_ffmpeg != value:
			self._download_ffmpeg = value
			self.downloadFfmpegChanged.emit()

	@Property(bool, constant=True)
	def hasGpu(self) -> bool:
		return self._has_gpu

	@Property(str, notify=languageChanged)
	def noGpuMessage(self) -> str:
		from srxy.i18n import tr as translate

		return translate("installer.no_gpu.banner")

	@Property(bool, notify=installSemanticChanged)
	def installSemantic(self) -> bool:
		return self._install_semantic

	@Slot(bool)
	def setInstallSemantic(self, value: bool):
		allowed = bool(value) and self._has_gpu
		if self._install_semantic != allowed:
			self._install_semantic = allowed
			self.installSemanticChanged.emit()
			if not allowed and self._prefetch_models:
				self._prefetch_models = False
				self.prefetchModelsChanged.emit()

	@Property(bool, notify=prefetchModelsChanged)
	def prefetchModels(self) -> bool:
		return self._prefetch_models

	@Slot(bool)
	def setPrefetchModels(self, value: bool):
		allowed = bool(value) and self._install_semantic
		if self._prefetch_models != allowed:
			self._prefetch_models = allowed
			self.prefetchModelsChanged.emit()

	@Property(bool, notify=addToPathChanged)
	def addToPath(self) -> bool:
		return self._add_to_path

	@Slot(bool)
	def setAddToPath(self, value: bool):
		flag = bool(value)
		if self._add_to_path != flag:
			self._add_to_path = flag
			self.addToPathChanged.emit()

	@Property(str, notify=languageChanged)
	def language(self) -> str:
		return self._language

	@Slot(str)
	def setLanguage(self, value: str):
		from srxy.application.settings import set_language_setting
		from srxy.i18n import get_language, set_language

		set_language(value)
		set_language_setting(value)
		self._language = get_language()
		self.languageChanged.emit()

	@Slot(str, result=str)
	def i18nTr(self, key: str) -> str:
		from srxy.i18n import tr as translate

		return translate(key)

	@Property(bool, notify=busyChanged)
	def busy(self) -> bool:
		return self._busy

	@Property(str, notify=statusChanged)
	def status(self) -> str:
		return self._status

	@Property(str, notify=errorChanged)
	def error(self) -> str:
		return self._error

	@Property(str, notify=progressLabelChanged)
	def progressLabel(self) -> str:
		return self._progress_label

	@Property(float, notify=progressValueChanged)
	def progressValue(self) -> float:
		return self._progress_value

	@Property(bool, notify=progressDeterminateChanged)
	def progressDeterminate(self) -> bool:
		return self._progress_determinate

	@Property(float, notify=overallProgressChanged)
	def overallProgressValue(self) -> float:
		return self._overall_progress_value

	@Property(str, notify=overallProgressChanged)
	def overallProgressText(self) -> str:
		if self._overall_total <= 0:
			return ""
		percent = int(round(self._overall_progress_value * 100))
		return translate(
			"installer.progress.overall_text",
			current=self._overall_index,
			total=self._overall_total,
			percent=percent,
		)

	@Property(str, notify=taskProgressChanged)
	def taskProgressText(self) -> str:
		if not self._progress_determinate:
			return ""
		percent = int(round(self._progress_value * 100))
		# Download callbacks report bytes; phase completion uses tiny totals like 1/1.
		if self._task_total >= 1024.0:
			return translate(
				"installer.progress.task_bytes",
				percent=percent,
				done=_format_byte_size(self._task_done),
				total=_format_byte_size(self._task_total),
			)
		return translate("installer.progress.percent", percent=percent)

	@Property(bool, notify=canGoBackChanged)
	def canGoBack(self) -> bool:
		if self._busy:
			return False
		if self._finished and self._mode in {"install", "reinstall"}:
			return False
		return True

	@Property(str, notify=pageChanged)
	def page(self) -> str:
		return self._page

	@Property(bool, notify=finishedChanged)
	def finished(self) -> bool:
		return self._finished

	@Property(bool, notify=unsafeConfirmChanged)
	def unsafeConfirmOpen(self) -> bool:
		return self._unsafe_confirm_open

	@Property(str, notify=unsafeConfirmChanged)
	def unsafeConfirmMessage(self) -> str:
		return self._unsafe_confirm_message

	@Property(str, notify=languageChanged)
	def privacyText(self) -> str:
		return privacy_disclaimer_html()

	@Property(str, notify=languageChanged)
	def privacyPlainText(self) -> str:
		return privacy_disclaimer_text()

	@Property(str, notify=languageChanged)
	def uninstallHint(self) -> str:
		return uninstall_search_hint()

	@Slot(str, result=str)
	def helpText(self, key: str) -> str:
		return help_text(key)

	@Slot()
	def goNext(self):
		self._error = ""
		self.errorChanged.emit()
		if self._mode == "uninstall":
			if self._page == "mode":
				self._page = "uninstall"
				self.pageChanged.emit()
			return
		order = ["mode", "prefix", "privacy", "options", "path", "progress"]
		try:
			index = order.index(self._page)
		except ValueError:
			return
		if self._page == "privacy" and not self._privacy_ack:
			self._error = translate("installer.error.privacy_ack")
			self.errorChanged.emit()
			return
		if index + 1 < len(order):
			self._page = order[index + 1]
			self.pageChanged.emit()

	@Slot()
	def goBack(self):
		if not self.canGoBack:
			return
		self._error = ""
		self.errorChanged.emit()
		if self._mode == "uninstall":
			if self._page == "progress":
				self._page = "uninstall"
				self.pageChanged.emit()
				self._finished = False
				self.finishedChanged.emit()
				return
			if self._page == "uninstall":
				self._page = "mode"
				self.pageChanged.emit()
			return
		order = ["mode", "prefix", "privacy", "options", "path", "progress"]
		try:
			index = order.index(self._page)
		except ValueError:
			return
		if index > 0:
			self._page = order[index - 1]
			self.pageChanged.emit()

	def _set_unsafe_confirm(self, open_: bool, message: str = "", *, action: str | None = None):
		self._unsafe_confirm_open = open_
		self._unsafe_confirm_message = message
		self._pending_unsafe_action = action if open_ else None
		self.unsafeConfirmChanged.emit()

	def _validate_prefix_for_action(self, prefix: Path, *, for_install: bool) -> str | None:
		"""Return an inline error message, or None if the prefix may proceed (or needs confirm)."""
		if for_install and is_non_empty_foreign_prefix(prefix):
			return translate("installer.error.non_empty_prefix", path=str(prefix))
		return None

	def _reset_progress_ui(self):
		self._progress_label = ""
		self.progressLabelChanged.emit()
		self._progress_value = 0.0
		self.progressValueChanged.emit()
		self._progress_determinate = False
		self.progressDeterminateChanged.emit()
		self._overall_index = 0
		self._overall_total = 0
		self._overall_progress_value = 0.0
		self._task_done = 0.0
		self._task_total = 0.0
		self.overallProgressChanged.emit()
		self.taskProgressChanged.emit()

	def _dispose_worker(self, *, wait_ms: int):
		"""Wait for the install/uninstall QThread and drop the Python ref.

		``_Worker`` is the QThread itself. Leaving it running (or GC'ing it while
		still finishing) SIGBUS/SIGSEGVs under pytest-xdist + PySide6.
		"""
		worker = self._worker
		self._worker = None
		if worker is None:
			return
		try:
			from shiboken6 import isValid

			if not isValid(worker):
				return
			if worker.isRunning():
				worker.requestInterruption()
				worker.wait(wait_ms)
		except RuntimeError:
			return

	def shutdown(self, *, thread_wait_ms: int = 3000):
		self._dispose_worker(wait_ms=thread_wait_ms)

	def _install_options(self, prefix: Path, *, confirm_unsafe: bool) -> InstallOptions:
		return InstallOptions(
			prefix=prefix,
			download_tesseract=self._download_tesseract,
			download_ffmpeg=self._download_ffmpeg,
			install_semantic=self._install_semantic and self._has_gpu,
			prefetch_models=self._prefetch_models and self._install_semantic,
			add_to_path=self._add_to_path,
			confirm_unsafe=confirm_unsafe,
		)

	def _begin_install(self, prefix: Path, *, confirm_unsafe: bool):
		self._dispose_worker(wait_ms=3000)
		self._page = "progress"
		self.pageChanged.emit()
		self._finished = False
		self.finishedChanged.emit()
		self.canGoBackChanged.emit()
		self._error = ""
		self.errorChanged.emit()
		self._reset_progress_ui()
		self._status = translate("installer.status.starting_install")
		self.statusChanged.emit()
		self._set_busy(True)
		options = self._install_options(prefix, confirm_unsafe=confirm_unsafe)
		self._worker = _Worker("install", options, None, confirm_unsafe=confirm_unsafe)
		self._worker.status.connect(self._on_status)
		self._worker.progress.connect(self._on_progress)
		self._worker.task.connect(self._on_task)
		self._worker.finished_ok.connect(self._on_finished_ok)
		self._worker.failed.connect(self._on_failed)
		self._worker.start()

	def _begin_reinstall(self, prefix: Path, *, confirm_unsafe: bool):
		self._dispose_worker(wait_ms=3000)
		self._page = "progress"
		self.pageChanged.emit()
		self._finished = False
		self.finishedChanged.emit()
		self.canGoBackChanged.emit()
		self._error = ""
		self.errorChanged.emit()
		self._reset_progress_ui()
		self._status = translate("installer.status.starting_reinstall")
		self.statusChanged.emit()
		self._set_busy(True)
		options = self._install_options(prefix, confirm_unsafe=confirm_unsafe)
		self._worker = _Worker("reinstall", options, prefix, confirm_unsafe=confirm_unsafe)
		self._worker.status.connect(self._on_status)
		self._worker.progress.connect(self._on_progress)
		self._worker.task.connect(self._on_task)
		self._worker.finished_ok.connect(self._on_finished_ok)
		self._worker.failed.connect(self._on_failed)
		self._worker.start()

	def _begin_uninstall(self, prefix: Path, *, confirm_unsafe: bool):
		self._dispose_worker(wait_ms=3000)
		self._page = "progress"
		self.pageChanged.emit()
		self._finished = False
		self.finishedChanged.emit()
		self.canGoBackChanged.emit()
		self._error = ""
		self.errorChanged.emit()
		self._reset_progress_ui()
		# Indeterminate spinner only — folder delete has no useful file progress.
		self._status = translate("installer.status.removing_app")
		self.statusChanged.emit()
		self._set_busy(True)
		self._worker = _Worker("uninstall", None, prefix, confirm_unsafe=confirm_unsafe)
		self._worker.status.connect(self._on_status)
		self._worker.finished_ok.connect(self._on_finished_ok)
		self._worker.failed.connect(self._on_failed)
		self._worker.start()

	@Slot()
	def startInstall(self):
		if self._busy or self._unsafe_confirm_open:
			return
		if not self._privacy_ack:
			self._error = translate("installer.error.privacy_required")
			self.errorChanged.emit()
			return
		if not self._prefix.strip():
			self._error = translate("installer.error.choose_prefix")
			self.errorChanged.emit()
			return
		prefix = Path(self._prefix).expanduser().resolve()
		foreign_error = self._validate_prefix_for_action(prefix, for_install=True)
		if foreign_error is not None:
			self._error = foreign_error
			self.errorChanged.emit()
			return
		if prefix_needs_confirmation(prefix) and not self._confirm_unsafe:
			self._error = ""
			self.errorChanged.emit()
			self._set_unsafe_confirm(
				True,
				translate("installer.confirm.unsafe_prefix_body", path=str(prefix)),
				action="install",
			)
			return
		self._begin_install(prefix, confirm_unsafe=self._confirm_unsafe)

	@Slot()
	def startReinstall(self):
		if self._busy or self._unsafe_confirm_open:
			return
		if not self._privacy_ack:
			self._error = translate("installer.error.privacy_required")
			self.errorChanged.emit()
			return
		if not self._prefix.strip():
			self._error = translate("installer.error.choose_prefix")
			self.errorChanged.emit()
			return
		prefix = Path(self._prefix).expanduser().resolve()
		if not is_srxy_prefix(prefix):
			self._error = translate("installer.error.reinstall_not_srxy")
			self.errorChanged.emit()
			return
		if prefix_needs_confirmation(prefix) and not self._confirm_unsafe:
			self._error = ""
			self.errorChanged.emit()
			self._set_unsafe_confirm(
				True,
				translate("installer.confirm.unsafe_prefix_body", path=str(prefix)),
				action="reinstall",
			)
			return
		self._begin_reinstall(prefix, confirm_unsafe=self._confirm_unsafe)

	@Slot()
	def startUninstall(self):
		if self._busy or self._unsafe_confirm_open:
			return
		raw = self._uninstall_prefix.strip() or self._prefix.strip()
		if not raw:
			discovered = discover_default_prefix()
			if discovered is None:
				self._error = f"{translate('installer.error.no_default_install')}\n\n{uninstall_search_hint()}"
				self.errorChanged.emit()
				return
			raw = str(discovered)
			self._uninstall_prefix = raw
			self.prefixChanged.emit()
		prefix = Path(raw).expanduser().resolve()
		if prefix_needs_confirmation(prefix) and not self._confirm_unsafe:
			self._error = ""
			self.errorChanged.emit()
			self._set_unsafe_confirm(
				True,
				translate("installer.confirm.unsafe_prefix_body", path=str(prefix)),
				action="uninstall",
			)
			return
		self._begin_uninstall(prefix, confirm_unsafe=self._confirm_unsafe)

	@Slot()
	def acceptUnsafeConfirm(self):
		action = self._pending_unsafe_action
		self._set_unsafe_confirm(False)
		self._confirm_unsafe = True
		if action == "install":
			prefix = Path(self._prefix).expanduser().resolve()
			self._begin_install(prefix, confirm_unsafe=True)
		elif action == "reinstall":
			prefix = Path(self._prefix).expanduser().resolve()
			self._begin_reinstall(prefix, confirm_unsafe=True)
		elif action == "uninstall":
			raw = self._uninstall_prefix.strip() or self._prefix.strip()
			self._begin_uninstall(Path(raw).expanduser().resolve(), confirm_unsafe=True)

	@Slot()
	def rejectUnsafeConfirm(self):
		self._set_unsafe_confirm(False)
		self._confirm_unsafe = False
		self._error = translate("installer.error.unsafe_prefix")
		self.errorChanged.emit()

	def _on_status(self, message: str):
		self._status = message
		self.statusChanged.emit()

	def _on_task(self, index: int, total: int, label: str):
		self._overall_index = max(0, index)
		self._overall_total = max(0, total)
		# Show completed fraction for prior phases; current phase fills via task bar.
		completed = max(0, index - 1)
		self._overall_progress_value = (completed / total) if total > 0 else 0.0
		self.overallProgressChanged.emit()
		self._status = label
		self.statusChanged.emit()
		# Phase text lives in status; task bar shows % / human sizes only.
		self._progress_label = ""
		self.progressLabelChanged.emit()
		self._progress_value = 0.0
		self._progress_determinate = False
		self._task_done = 0.0
		self._task_total = 0.0
		self.progressValueChanged.emit()
		self.progressDeterminateChanged.emit()
		self.taskProgressChanged.emit()

	def _on_progress(self, done: float, total: float, label: str):
		del label  # Ignore technical download names; show human sizes in taskProgressText.
		self._task_done = max(0.0, float(done))
		self._task_total = max(0.0, float(total))
		if self._task_total > 0:
			fraction = min(1.0, self._task_done / self._task_total)
			self._progress_value = fraction
			self._progress_determinate = True
			# Smooth overall: prior phases + current task fraction.
			if self._overall_total > 0:
				completed = max(0, self._overall_index - 1)
				self._overall_progress_value = min(1.0, (completed + fraction) / self._overall_total)
				self.overallProgressChanged.emit()
		else:
			self._progress_value = 0.0
			self._progress_determinate = False
		self.progressValueChanged.emit()
		self.progressDeterminateChanged.emit()
		self.taskProgressChanged.emit()

	def _on_finished_ok(self):
		self._set_busy(False)
		self._finished = True
		self.finishedChanged.emit()
		self.canGoBackChanged.emit()
		self._progress_label = ""
		self.progressLabelChanged.emit()
		self._progress_value = 1.0
		self._progress_determinate = True
		self._task_done = 0.0
		self._task_total = 0.0
		self.progressValueChanged.emit()
		self.progressDeterminateChanged.emit()
		if self._overall_total > 0:
			self._overall_index = self._overall_total
		self._overall_progress_value = 1.0
		self.overallProgressChanged.emit()
		self.taskProgressChanged.emit()
		if self._mode == "reinstall":
			self._status = translate("installer.status.reinstall_complete")
		elif self._mode == "uninstall":
			self._status = translate("installer.status.uninstall_complete")
		else:
			self._status = translate("installer.status.install_complete")
		self.statusChanged.emit()
		self.shutdown()

	def _on_failed(self, message: str):
		self._set_busy(False)
		self._error = message
		self.errorChanged.emit()
		self._status = translate("installer.status.failed")
		self.statusChanged.emit()
		self.shutdown()

	def wait_for_worker_for_tests(self, *, wait_ms: int = 5000) -> bool:
		"""Test helper — block until the background install worker has stopped."""
		worker = self._worker
		if worker is None:
			return True
		if not worker.isRunning():
			return True
		return bool(worker.wait(wait_ms))


__all__ = ["InstallerController"]
