"""PySide6 controller for the install / uninstall wizard."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, QThread, Signal, Slot

from srxy.adapters.inbound.installer.gpu import has_accelerated_gpu
from srxy.adapters.inbound.installer.help_text import help_text
from srxy.adapters.inbound.installer.install import InstallOptions, install_srxy
from srxy.adapters.inbound.installer.privacy import privacy_disclaimer_html, privacy_disclaimer_text
from srxy.adapters.inbound.installer.uninstall import (
	UNINSTALL_SEARCH_HINT,
	discover_default_prefix,
	uninstall_prefix,
)
from srxy.application.install_paths import default_install_prefix


class _Worker(QThread):
	status = Signal(str)
	progress = Signal(int, int, str)
	finished_ok = Signal()
	failed = Signal(str)

	def __init__(self, action: str, options: InstallOptions | None, prefix: Path | None):
		super().__init__()
		self._action = action
		self._options = options
		self._prefix = prefix

	def run(self):
		try:
			if self._action == "install":
				if self._options is None:
					raise RuntimeError("install requires options")
				install_srxy(
					self._options,
					status=lambda message: self.status.emit(message),
					progress=lambda done, total, label: self.progress.emit(done, total, label),
				)
			elif self._action == "uninstall":
				if self._prefix is None:
					raise RuntimeError("uninstall requires a prefix")
				uninstall_prefix(self._prefix, status=lambda message: self.status.emit(message))
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
	pageChanged = Signal()
	finishedChanged = Signal()

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
		self._page = "mode"
		self._finished = False
		self._uninstall_hint = UNINSTALL_SEARCH_HINT
		self._worker: _Worker | None = None
		discovered = discover_default_prefix()
		if discovered is not None:
			self._uninstall_prefix = str(discovered)
		else:
			self._uninstall_prefix = ""

	def _set_busy(self, value: bool):
		if self._busy != value:
			self._busy = value
			self.busyChanged.emit()

	@Property(str, notify=modeChanged)
	def mode(self) -> str:
		return self._mode

	@Slot(str)
	def setMode(self, value: str):
		if value not in {"install", "uninstall"}:
			return
		if self._mode != value:
			self._mode = value
			self.modeChanged.emit()

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

	@Property(str, notify=pageChanged)
	def page(self) -> str:
		return self._page

	@Property(bool, notify=finishedChanged)
	def finished(self) -> bool:
		return self._finished

	@Property(str, notify=languageChanged)
	def privacyText(self) -> str:
		return privacy_disclaimer_html()

	@Property(str, notify=languageChanged)
	def privacyPlainText(self) -> str:
		return privacy_disclaimer_text()

	@Property(str, constant=True)
	def uninstallHint(self) -> str:
		return self._uninstall_hint

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
			self._error = "Please check the box to continue — it confirms you read the notice."
			self.errorChanged.emit()
			return
		if index + 1 < len(order):
			self._page = order[index + 1]
			self.pageChanged.emit()

	@Slot()
	def goBack(self):
		self._error = ""
		self.errorChanged.emit()
		if self._mode == "uninstall":
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

	@Slot()
	def startInstall(self):
		if self._busy:
			return
		if not self._privacy_ack:
			self._error = "Please acknowledge the privacy / third-party notice to continue."
			self.errorChanged.emit()
			return
		prefix = Path(self._prefix).expanduser()
		if not self._prefix.strip():
			self._error = "Choose an install folder."
			self.errorChanged.emit()
			return
		self._page = "progress"
		self.pageChanged.emit()
		self._finished = False
		self.finishedChanged.emit()
		self._error = ""
		self.errorChanged.emit()
		self._status = "Starting install…"
		self.statusChanged.emit()
		self._set_busy(True)
		options = InstallOptions(
			prefix=prefix,
			download_tesseract=self._download_tesseract,
			download_ffmpeg=self._download_ffmpeg,
			install_semantic=self._install_semantic and self._has_gpu,
			prefetch_models=self._prefetch_models and self._install_semantic,
			add_to_path=self._add_to_path,
		)
		self._worker = _Worker("install", options, None)
		self._worker.status.connect(self._on_status)
		self._worker.progress.connect(self._on_progress)
		self._worker.finished_ok.connect(self._on_finished_ok)
		self._worker.failed.connect(self._on_failed)
		self._worker.start()

	@Slot()
	def startUninstall(self):
		if self._busy:
			return
		raw = self._uninstall_prefix.strip() or self._prefix.strip()
		if not raw:
			discovered = discover_default_prefix()
			if discovered is None:
				self._error = f"No install found at the default location.\n\n{UNINSTALL_SEARCH_HINT}"
				self.errorChanged.emit()
				return
			raw = str(discovered)
			self._uninstall_prefix = raw
			self.prefixChanged.emit()
		self._page = "progress"
		self.pageChanged.emit()
		self._finished = False
		self.finishedChanged.emit()
		self._error = ""
		self.errorChanged.emit()
		self._status = "Starting uninstall…"
		self.statusChanged.emit()
		self._set_busy(True)
		self._worker = _Worker("uninstall", None, Path(raw))
		self._worker.status.connect(self._on_status)
		self._worker.finished_ok.connect(self._on_finished_ok)
		self._worker.failed.connect(self._on_failed)
		self._worker.start()

	def _on_status(self, message: str):
		self._status = message
		self.statusChanged.emit()

	def _on_progress(self, done: int, total: int, label: str):
		self._progress_label = label
		self.progressLabelChanged.emit()
		if total > 0:
			self._progress_value = min(1.0, done / total)
		else:
			self._progress_value = 0.0
		self.progressValueChanged.emit()

	def _on_finished_ok(self):
		self._set_busy(False)
		self._finished = True
		self.finishedChanged.emit()
		self._status = "Done."
		self.statusChanged.emit()

	def _on_failed(self, message: str):
		self._set_busy(False)
		self._error = message
		self.errorChanged.emit()
		self._status = "Failed."
		self.statusChanged.emit()


__all__ = ["InstallerController"]
