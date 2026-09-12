"""Perform a prefix install of srxy (uv venv + optional vendor/semantic)."""

from __future__ import annotations

import os
import platform
import plistlib
import queue
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from importlib.metadata import version as package_version
from pathlib import Path

from srxy.adapters.inbound.installer.cancel import InstallCancelledError, raise_if_cancelled
from srxy.adapters.inbound.installer.cuda_torch import (
	ensure_windows_cuda_torch,
	should_ensure_windows_cuda_torch,
)
from srxy.adapters.inbound.installer.download import ProgressCallback
from srxy.adapters.inbound.installer.manifest import (
	InstallManifest,
	is_non_empty_foreign_prefix,
	is_srxy_prefix,
	looks_like_partial_srxy_prefix,
	prefix_needs_confirmation,
	utc_now_iso,
	write_manifest,
)
from srxy.adapters.inbound.installer.meta import load_installer_meta
from srxy.adapters.inbound.installer.package_spec import resolve_srxy_install_spec, with_extras
from srxy.adapters.inbound.installer.privacy import PRIVACY_NOTICE_VERSION
from srxy.adapters.inbound.installer.vendor import install_ffmpeg, install_tesseract, install_uv
from srxy.adapters.outbound.models.model_store import parse_progress_line
from srxy.application.install_paths import MANIFEST_NAME
from srxy.i18n import tr
from srxy.resources.icons import app_icon_path, available_icon_sizes, macos_app_icon_path
from srxy.resources.macos import app_launcher_c_path


StatusCallback = Callable[[str], None]
# index (1-based current phase), total phases, phase label
TaskCallback = Callable[[int, int, str], None]

_PIP_PROGRESS_RE = re.compile(r"(\d+)\s*%|(\d+)\s*/\s*(\d+)")
_HEARTBEAT_SECONDS = 2.0


@dataclass(slots=True)
class InstallOptions:
	prefix: Path
	download_tesseract: bool = True
	download_ffmpeg: bool = True
	install_semantic: bool = False
	prefetch_models: bool = False
	add_to_path: bool = True
	srxy_spec: str = ""
	confirm_unsafe: bool = False
	tessdata_langs: tuple[str, ...] = ()
	ui_language: str | None = None


@dataclass(frozen=True, slots=True)
class InstallPhase:
	key: str
	label: str


def plan_install_phases(options: InstallOptions) -> list[InstallPhase]:
	"""Major install phases for overall progress (optional steps omitted when disabled)."""
	phases = [
		InstallPhase("uv", tr("installer.status.installing_uv")),
		InstallPhase("venv", tr("installer.status.creating_venv")),
		InstallPhase("package", tr("installer.status.installing_package", spec="srxy")),
	]
	if should_ensure_windows_cuda_torch(
		install_semantic=options.install_semantic,
		is_windows=_is_windows(),
	):
		phases.append(InstallPhase("cuda_torch", tr("installer.status.installing_cuda_torch")))
	if options.download_tesseract:
		phases.append(InstallPhase("tesseract", tr("installer.status.downloading_tesseract")))
	if options.download_ffmpeg:
		phases.append(InstallPhase("ffmpeg", tr("installer.status.downloading_ffmpeg")))
	if options.install_semantic and options.prefetch_models:
		phases.append(InstallPhase("models", tr("installer.status.prefetching_models")))
	phases.append(InstallPhase("launcher", tr("installer.status.writing_launcher")))
	if options.add_to_path:
		phases.append(InstallPhase("path", tr("installer.status.adding_path")))
	return phases


def _status(callback: StatusCallback | None, message: str):
	if callback is not None:
		callback(message)


def _task(
	callback: TaskCallback | None,
	*,
	index: int,
	total: int,
	label: str,
):
	if callback is not None:
		callback(index, total, label)


def _raise_if_cancelled(cancel_file: str | None):
	raise_if_cancelled(cancel_file, tr("installer.status.cancelled"))


def _run(cmd: list[str], *, env: dict[str, str] | None = None, cancel_file: str | None = None) -> None:
	_raise_if_cancelled(cancel_file)
	result = subprocess.run(  # noqa: S603
		cmd,
		capture_output=True,
		text=True,
		check=False,
		env=env,
	)
	if result.returncode != 0:
		detail = (result.stderr or result.stdout or "").strip()
		raise RuntimeError(f"command failed ({result.returncode}): {' '.join(cmd)}\n{detail}")


def _emit_pip_line_progress(
	line: str,
	*,
	progress: ProgressCallback | None,
	default_label: str,
) -> None:
	if progress is None:
		return
	text = line.strip()
	if not text:
		return
	match = _PIP_PROGRESS_RE.search(text)
	if match is None:
		return
	if match.group(1) is not None:
		done = int(match.group(1))
		progress(done, 100, default_label)
		return
	if match.group(2) is not None and match.group(3) is not None:
		done = int(match.group(2))
		total = int(match.group(3))
		if total > 0:
			progress(done, total, default_label)


def _run_with_stdout_progress(
	cmd: list[str],
	*,
	env: dict[str, str] | None = None,
	progress: ProgressCallback | None = None,
	cancel_file: str | None = None,
	heartbeat_label: str = "",
) -> None:
	_raise_if_cancelled(cancel_file)
	proc = subprocess.Popen(  # noqa: S603
		cmd,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		text=True,
		env=env,
	)
	stdout = proc.stdout
	stderr = proc.stderr
	if stdout is None or stderr is None:
		raise RuntimeError("command failed: missing stdout/stderr pipes")

	out_q: queue.Queue[tuple[str, str]] = queue.Queue()

	def pump(stream: Iterator[str], name: str):
		for line in stream:
			out_q.put((name, line))
		out_q.put((name, ""))

	threads = [
		threading.Thread(target=pump, args=(stdout, "stdout"), daemon=True),
		threading.Thread(target=pump, args=(stderr, "stderr"), daemon=True),
	]
	for thread in threads:
		thread.start()

	label = heartbeat_label or " ".join(cmd)
	stderr_chunks: list[str] = []
	open_streams = 2
	last_heartbeat = time.monotonic()

	while open_streams > 0:
		_raise_if_cancelled(cancel_file)
		try:
			name, line = out_q.get(timeout=0.2)
		except queue.Empty:
			if progress is not None and heartbeat_label and time.monotonic() - last_heartbeat >= _HEARTBEAT_SECONDS:
				progress(0, 0, heartbeat_label)
				last_heartbeat = time.monotonic()
			if proc.poll() is not None and out_q.empty():
				open_streams = 0
			continue
		if line == "":
			open_streams -= 1
			continue
		last_heartbeat = time.monotonic()
		if name == "stderr":
			stderr_chunks.append(line)
		else:
			_emit_pip_line_progress(line, progress=progress, default_label=label)

	code = proc.wait()
	if code != 0:
		detail = "".join(stderr_chunks).strip()
		raise RuntimeError(f"command failed ({code}): {' '.join(cmd)}\n{detail}")


def _run_with_progress(
	cmd: list[str],
	*,
	env: dict[str, str] | None = None,
	progress: ProgressCallback | None = None,
	cancel_file: str | None = None,
) -> None:
	"""Run a command and forward ``__SRXY_PROGRESS__`` stdout lines to ``progress``."""
	_raise_if_cancelled(cancel_file)
	proc = subprocess.Popen(  # noqa: S603
		cmd,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		text=True,
		env=env,
	)
	stdout = proc.stdout
	stderr = proc.stderr
	if stdout is None or stderr is None:
		raise RuntimeError("command failed: missing stdout/stderr pipes")
	stderr_chunks: list[str] = []
	for line in stdout:
		_raise_if_cancelled(cancel_file)
		parsed = parse_progress_line(line)
		if parsed is not None:
			done, total, label = parsed
			if progress is not None:
				progress(done, total, label)
			continue
		# Non-progress stdout is ignored for UI; keep for failure detail.
		stderr_chunks.append(line)
	err = stderr.read()
	if err:
		stderr_chunks.append(err)
	code = proc.wait()
	if code != 0:
		detail = "".join(stderr_chunks).strip()
		raise RuntimeError(f"command failed ({code}): {' '.join(cmd)}\n{detail}")


def _validate_install_prefix(prefix: Path, *, confirm_unsafe: bool):
	if prefix_needs_confirmation(prefix) and not confirm_unsafe:
		raise RuntimeError(tr("installer.error.unsafe_prefix"))
	if is_non_empty_foreign_prefix(prefix) and not looks_like_partial_srxy_prefix(prefix):
		raise RuntimeError(tr("installer.error.non_empty_prefix", path=str(prefix)))


def _clear_macos_qml_caches():
	"""Drop Qt QML disk caches that can keep pre-style-fix bytecode on Darwin."""
	if platform.system().lower() != "darwin":
		return
	home = Path.home()
	for relative in (
		Path("Library") / "Caches" / "srxy" / "qmlcache",
		Path("Library") / "Caches" / "srxy-installer" / "qmlcache",
		Path("Library") / "Caches" / "Python" / "qmlcache",
	):
		cache = home / relative
		if cache.is_dir():
			shutil.rmtree(cache, ignore_errors=True)


def write_launcher(prefix: Path):
	bin_dir = prefix / "bin"
	bin_dir.mkdir(parents=True, exist_ok=True)
	log_dir = prefix / "logs"
	log_dir.mkdir(parents=True, exist_ok=True)
	if _is_windows():
		_write_windows_launcher(prefix)
		return
	venv_srxy = prefix / ".venv" / "bin" / "srxy"
	launcher = bin_dir / "srxy"
	vendor_bin_parts = [
		shlex.quote((prefix / "vendor" / "tesseract" / "bin").as_posix()),
		shlex.quote((prefix / "vendor" / "ffmpeg" / "bin").as_posix()),
		shlex.quote((prefix / "vendor" / "uv").as_posix()),
	]
	path_prefix = ":".join(vendor_bin_parts)
	tessdata = prefix / "vendor" / "tesseract" / "tessdata"
	tessdata_dist = prefix / "vendor" / "tesseract" / "dist" / "tessdata"
	log_file = log_dir / "srxy.log"
	q_prefix = shlex.quote(prefix.as_posix())
	q_venv = shlex.quote(venv_srxy.as_posix())
	q_log_dir = shlex.quote(log_dir.as_posix())
	q_log_file = shlex.quote(log_file.as_posix())
	q_tessdata = shlex.quote(tessdata.as_posix())
	content = f"""#!/bin/sh
set -eu
SRXY_HOME={q_prefix}
export SRXY_HOME
export PATH="{path_prefix}:$PATH"
if [ -d {shlex.quote(tessdata_dist.as_posix())} ]; then
	export TESSDATA_PREFIX={shlex.quote(tessdata_dist.as_posix())}
else
	export TESSDATA_PREFIX={q_tessdata}
fi
# Force native Quick Controls before Python starts (Finder launches inherit a
# minimal env; without this some hosts fall back to Basic/Fusion chrome).
case "$(uname -s 2>/dev/null || true)" in
Darwin)
	export QT_QUICK_CONTROLS_STYLE="${{QT_QUICK_CONTROLS_STYLE:-macOS}}"
	;;
esac
LOG_DIR={q_log_dir}
LOG_FILE={q_log_file}
mkdir -p "$LOG_DIR"
_log_start() {{
	{{
		echo "===== $(date -Iseconds 2>/dev/null || date) srxy start ====="
		if [ "${{SRXY_DEBUG:-}}" = "1" ]; then
			echo "argv: $*"
		fi
		echo "SRXY_HOME=$SRXY_HOME"
		echo "QT_QUICK_CONTROLS_STYLE=${{QT_QUICK_CONTROLS_STYLE:-}}"
	}} >>"$LOG_FILE"
}}
if [ -t 1 ]; then
	_log_start "$@"
	exec {q_venv} "$@"
else
	_log_start "$@"
	exec {q_venv} "$@" >>"$LOG_FILE" 2>&1
fi
"""
	launcher.write_text(content, encoding="utf-8")
	launcher.chmod(0o755)
	_write_macos_app(prefix, launcher_text=content)
	_clear_macos_qml_caches()


def _write_windows_launcher(prefix: Path):
	"""Write ``bin\\srxy.cmd`` (CLI/PATH) and ``bin\\Srxy.exe`` (GUI shortcuts)."""
	bin_dir = prefix / "bin"
	venv_srxy = prefix / ".venv" / "Scripts" / "srxy.exe"
	launcher = bin_dir / "srxy.cmd"
	vendor_tess = prefix / "vendor" / "tesseract" / "bin"
	vendor_ffmpeg = prefix / "vendor" / "ffmpeg" / "bin"
	vendor_uv = prefix / "vendor" / "uv"
	tessdata = prefix / "vendor" / "tesseract" / "tessdata"
	log_dir = prefix / "logs"
	log_file = log_dir / "srxy.log"
	# Use delayed expansion carefully; prefer explicit setlocal for PATH mutation.
	content = f"""@echo off
setlocal EnableExtensions
set "SRXY_HOME={prefix}"
set "PATH={vendor_tess};{vendor_ffmpeg};{vendor_uv};%PATH%"
if exist "{prefix}\\vendor\\tesseract\\dist\\tessdata" (
	set "TESSDATA_PREFIX={prefix}\\vendor\\tesseract\\dist\\tessdata"
) else (
	set "TESSDATA_PREFIX={tessdata}"
)
if not exist "{log_dir}" mkdir "{log_dir}"
>>"{log_file}" echo ===== %DATE% %TIME% srxy start =====
>>"{log_file}" echo SRXY_HOME=%SRXY_HOME%
"{venv_srxy}" %*
set "EXITCODE=%ERRORLEVEL%"
exit /b %EXITCODE%
"""
	launcher.write_text(content, encoding="utf-8")
	# Convenience shim without extension for tooling that looks for ``bin/srxy``.
	shim = bin_dir / "srxy"
	if not shim.exists():
		shim.write_text(content, encoding="utf-8")
	_write_windows_gui_exe(prefix)


def _find_csc() -> Path | None:
	roots = [
		Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET" / "Framework64",
		Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET" / "Framework",
	]
	for root in roots:
		if not root.is_dir():
			continue
		versions = sorted(
			(p for p in root.iterdir() if p.is_dir() and p.name.startswith("v")),
			key=lambda p: p.name,
			reverse=True,
		)
		for version_dir in versions:
			csc = version_dir / "csc.exe"
			if csc.is_file():
				return csc
	return None


def _packaged_windows_ico(*, installer: bool = False) -> Path | None:
	from importlib import resources

	name = "srxy-installer.ico" if installer else "srxy.ico"
	path = Path(str(resources.files("srxy.resources.icons").joinpath(name)))
	return path if path.is_file() else None


def _write_windows_ico(path: Path, *, installer: bool = False):
	"""Write a multi-size .ico (copy packaged asset, else generate via Pillow)."""
	path.parent.mkdir(parents=True, exist_ok=True)
	packaged = _packaged_windows_ico(installer=installer)
	if packaged is not None:
		shutil.copy2(packaged, path)
		return
	from PIL import Image

	from srxy.resources.icons import installer_icon_path

	sizes = (16, 32, 48, 64, 128, 256)
	images: list[Image.Image] = []
	for size in sizes:
		source = installer_icon_path(size=size) if installer else app_icon_path(size=size)
		images.append(Image.open(source).convert("RGBA"))
	# Primary must be the largest. Pillow default PNG-in-ICO keeps size down.
	images[-1].save(
		path,
		format="ICO",
		sizes=[(img.width, img.height) for img in images],
		append_images=images[:-1],
	)


def _launcher_cs_source() -> Path:
	from importlib import resources

	return Path(str(resources.files("srxy.resources").joinpath("windows/SrxyLauncher.cs")))


def _write_windows_gui_exe(prefix: Path):
	"""Compile or copy ``bin\\Srxy.exe`` with the app icon for Start Menu / desktop."""
	bin_dir = prefix / "bin"
	bin_dir.mkdir(parents=True, exist_ok=True)
	dest = bin_dir / "Srxy.exe"
	icons_dir = prefix / "share" / "icons"
	ico = icons_dir / "srxy.ico"
	_write_windows_ico(ico, installer=False)

	payload = os.environ.get("SRXY_INSTALLER_PAYLOAD", "").strip()
	if payload:
		prebuilt = Path(payload) / "share" / "srxy" / "windows" / "Srxy.exe"
		if prebuilt.is_file():
			shutil.copy2(prebuilt, dest)
			return

	csc = _find_csc()
	cs_path = _launcher_cs_source()
	if csc is None or not cs_path.is_file():
		raise RuntimeError(
			"Unable to build Srxy.exe launcher (csc.exe or SrxyLauncher.cs missing). "
			"Install .NET Framework 4.x developer pack tools, or rebuild the offline installer."
		)
	cmd = [
		str(csc),
		"/nologo",
		"/target:winexe",
		f"/win32icon:{ico}",
		"/reference:System.Windows.Forms.dll",
		f"/out:{dest}",
		str(cs_path),
	]
	subprocess.run(cmd, check=True, capture_output=True, text=True)  # noqa: S603


# AppKit gates Tahoe Liquid Glass on the *main executable* linked SDK
# (LC_BUILD_VERSION), not Info.plist. Keep minos aligned with LSMinimumSystemVersion.
_MACOS_EMBEDDED_PYTHON_MINOS = "12.0"
_MACOS_EMBEDDED_PYTHON_SDK = "26.0"
_MACHO_MAGICS = {
	b"\xcf\xfa\xed\xfe",
	b"\xfe\xed\xfa\xcf",
	b"\xca\xfe\xba\xbe",
	b"\xbe\xba\xfe\xca",
}


def _is_macho_executable(path: Path) -> bool:
	try:
		return path.read_bytes()[:4] in _MACHO_MAGICS
	except OSError:
		return False


def _restamp_macos_linked_sdk(
	binary: Path,
	*,
	minos: str = _MACOS_EMBEDDED_PYTHON_MINOS,
	sdk: str = _MACOS_EMBEDDED_PYTHON_SDK,
) -> bool:
	"""Rewrite ``LC_BUILD_VERSION`` so AppKit draws modern Tahoe chrome.

	Returns True when the binary was restamped. Non-Mach-O inputs (test stubs)
	are skipped. Missing ``vtool`` on Darwin is a hard error for real interpreters.
	"""
	if not _is_macho_executable(binary):
		return False
	xcrun = shutil.which("xcrun")
	vtool = shutil.which("vtool")
	if xcrun is not None:
		cmd_prefix = [xcrun, "vtool"]
	elif vtool is not None:
		cmd_prefix = [vtool]
	else:
		raise RuntimeError(
			"vtool is required to stamp embedded SrxyPython with macOS SDK "
			f"{sdk} (Liquid Glass). Install Xcode CLT or ensure vtool is on PATH."
		)
	tmp = binary.with_name(binary.name + ".restamp")
	cmd = [
		*cmd_prefix,
		"-set-build-version",
		"macos",
		minos,
		sdk,
		"-replace",
		"-output",
		str(tmp),
		str(binary),
	]
	completed = subprocess.run(cmd, check=False, capture_output=True, text=True)  # noqa: S603
	if completed.returncode != 0 or not tmp.is_file():
		tmp.unlink(missing_ok=True)
		detail = (completed.stderr or completed.stdout or "").strip()
		raise RuntimeError(f"vtool failed restamping {binary.name} to sdk {sdk}: {detail}")
	tmp.replace(binary)
	binary.chmod(0o755)
	return True


def _adhoc_codesign_macos(binary: Path):
	"""Re-sign after vtool (invalidates the previous signature)."""
	codesign = shutil.which("codesign") or "/usr/bin/codesign"
	if not Path(codesign).is_file():
		print(f"warning: codesign not found; left {binary.name} unsigned after SDK restamp", file=sys.stderr)
		return
	completed = subprocess.run(  # noqa: S603
		[codesign, "--force", "--sign", "-", "--timestamp=none", str(binary)],
		check=False,
		capture_output=True,
		text=True,
	)
	if completed.returncode != 0:
		detail = (completed.stderr or completed.stdout or "").strip()
		print(f"warning: ad-hoc codesign failed for {binary.name}: {detail}", file=sys.stderr)


def _embed_macos_app_python(prefix: Path, macos_dir: Path) -> Path | None:
	"""Place a Python interpreter *inside* ``Srxy.app`` so AppKit keeps our bundle.

	Finder launches Mach-O ``Contents/MacOS/srxy``, which ``exec``s an interpreter
	whose path still lives under ``Srxy.app``. If we ``exec`` the prefix ``.venv``
	python (outside the bundle), ``NSBundle.mainBundle`` becomes the uv/CPython
	install.

	Always **copy** (never hardlink): we then ``vtool``-restamp the copy to
	linked SDK 26 so Tahoe draws Liquid Glass instead of legacy Aqua. Hardlinking
	would mutate the shared uv CPython install under ``~/.local/share/uv/python``.
	"""
	venv_python = prefix / ".venv" / "bin" / "python"
	if not venv_python.exists():
		return None
	real_python = venv_python.resolve()
	embedded = macos_dir / "SrxyPython"
	if embedded.exists() or embedded.is_symlink():
		embedded.unlink()
	shutil.copy2(real_python, embedded)
	embedded.chmod(0o755)
	# Only restamp on a real Darwin host with a real Mach-O interpreter.
	if sys.platform == "darwin" and _is_macho_executable(embedded):
		_restamp_macos_linked_sdk(embedded)
		_adhoc_codesign_macos(embedded)
	return embedded


def _venv_site_packages(prefix: Path) -> Path | None:
	lib = prefix / ".venv" / "lib"
	if not lib.is_dir():
		return None
	candidates = sorted(p for p in lib.glob("python*/site-packages") if p.is_dir())
	return candidates[0] if candidates else None


def _c_string_define(value: str) -> str:
	"""Return a clang ``-DNAME="…"`` value with escapes for backslash and quotes."""
	escaped = value.replace("\\", "\\\\").replace('"', '\\"')
	return f'"{escaped}"'


def _venv_python_home(prefix: Path) -> str | None:
	"""Return ``sys.base_prefix`` for the prefix venv interpreter (for PYTHONHOME)."""
	venv_python = prefix / ".venv" / "bin" / "python"
	if not venv_python.exists():
		return None
	try:
		out = subprocess.check_output(  # noqa: S603
			[str(venv_python), "-c", "import sys; print(sys.base_prefix)"],
			text=True,
			stderr=subprocess.DEVNULL,
		)
	except (OSError, subprocess.CalledProcessError):
		return None
	home = out.strip()
	if not home:
		return None
	return str(Path(home).resolve())


def _compile_macos_app_launcher(prefix: Path, dest: Path):
	"""Compile Mach-O ``CFBundleExecutable`` (macOS rejects shell scripts)."""
	src = app_launcher_c_path()
	if not src.is_file():
		raise FileNotFoundError(f"missing macOS app launcher source: {src}")

	site = _venv_site_packages(prefix)
	if site is None:
		# Editable / partial prefixes: still point at the expected layout.
		site = prefix / ".venv" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"

	python_home = _venv_python_home(prefix)
	if not python_home:
		# Fall back to the resolved interpreter's parent chain when probe fails.
		venv_python = prefix / ".venv" / "bin" / "python"
		python_home = str(venv_python.resolve().parent.parent) if venv_python.exists() else ""
	if not python_home:
		raise RuntimeError("could not resolve PYTHONHOME for Srxy.app launcher")

	tessdata = prefix / "vendor" / "tesseract" / "tessdata"
	tessdata_dist = prefix / "vendor" / "tesseract" / "dist" / "tessdata"
	tess = tessdata_dist if tessdata_dist.is_dir() else tessdata
	path_prefix = ":".join(
		[
			(prefix / "vendor" / "tesseract" / "bin").as_posix(),
			(prefix / "vendor" / "ffmpeg" / "bin").as_posix(),
			(prefix / "vendor" / "uv").as_posix(),
		]
	)
	log_dir = prefix / "logs"
	log_dir.mkdir(parents=True, exist_ok=True)
	log_file = log_dir / "srxy.log"

	clang = shutil.which("clang")
	if clang is None:
		raise RuntimeError("clang is required to build Srxy.app (CFBundleExecutable must be Mach-O)")

	cmd = [
		clang,
		"-O2",
		"-Wall",
		"-Wextra",
		f"-DSRXY_HOME_PATH={_c_string_define(prefix.as_posix())}",
		f"-DSRXY_PYTHONHOME={_c_string_define(python_home)}",
		f"-DSRXY_SITE_PACKAGES={_c_string_define(site.as_posix())}",
		f"-DSRXY_PATH_PREFIX={_c_string_define(path_prefix)}",
		f"-DSRXY_TESSDATA={_c_string_define(tess.as_posix())}",
		f"-DSRXY_LOG_FILE={_c_string_define(log_file.as_posix())}",
		"-o",
		str(dest),
		str(src),
	]
	completed = subprocess.run(cmd, check=False, capture_output=True, text=True)  # noqa: S603
	if completed.returncode != 0:
		detail = (completed.stderr or completed.stdout or "").strip()
		raise RuntimeError(f"clang failed building Srxy.app launcher: {detail}")
	dest.chmod(0o755)
	_adhoc_codesign_macos(dest)


def _write_macos_bundle_executable(prefix: Path, dest: Path):
	"""Write ``Contents/MacOS/srxy`` as Mach-O (or a non-shell stub off Darwin)."""
	# Cross-platform tests monkeypatch ``platform.system`` to Darwin; only compile
	# on a real macOS host. Stub must not look like a shell script — LaunchServices
	# rejects ``#!/bin/sh`` as ``CFBundleExecutable`` (kLSNoExecutableErr).
	if sys.platform != "darwin":
		dest.write_bytes(b"\xcf\xfa\xed\xfeSRXY_MACOS_LAUNCHER_STUB\n")
		dest.chmod(0o755)
		return
	_compile_macos_app_launcher(prefix, dest)


def _write_macos_app(prefix: Path, *, launcher_text: str):
	# ``launcher_text`` is the CLI ``bin/srxy`` shell script. The .app bundle
	# executable must be Mach-O — LaunchServices rejects shell scripts
	# (kLSNoExecutableErr / Dock "(null)").
	_ = launcher_text
	if platform.system().lower() != "darwin":
		return
	app_bundle = prefix / "Srxy.app"
	macos_dir = app_bundle / "Contents" / "MacOS"
	resources_dir = app_bundle / "Contents" / "Resources"
	macos_dir.mkdir(parents=True, exist_ok=True)
	resources_dir.mkdir(parents=True, exist_ok=True)

	_embed_macos_app_python(prefix, macos_dir)
	_write_macos_bundle_executable(prefix, macos_dir / "srxy")

	# Prefer squircle-masked macOS artwork so Finder/Dock show rounded corners.
	icon_png = macos_app_icon_path()
	shutil.copy2(icon_png, resources_dir / "srxy.png")
	icns_name = "srxy.icns"
	icns_path = resources_dir / icns_name
	try:
		# Deferred: Pillow is a macOS-only runtime need here (Windows offline
		# installer venv installs srxy with ``--no-deps``, so importing this
		# at module load time breaks the Windows relocatable-venv smoke test).
		from srxy.resources.icons.icns import write_icns_from_png

		write_icns_from_png(icon_png, icns_path)
	except Exception as exc:  # noqa: BLE001 — icon is best-effort; app still launches
		print(f"warning: could not write {icns_path.name}: {exc}", file=sys.stderr)
		if icns_path.exists():
			icns_path.unlink(missing_ok=True)

	# Keep modern Tahoe metrics: do NOT set UIDesignRequiresCompatibility.
	plist: dict[str, object] = {
		"CFBundleName": "Srxy",
		"CFBundleDisplayName": "Srxy",
		"CFBundleIdentifier": "com.srxy.app",
		"CFBundleVersion": "1",
		"CFBundleShortVersionString": "1",
		"CFBundleExecutable": "srxy",
		"CFBundlePackageType": "APPL",
		"LSMinimumSystemVersion": "12.0",
		"NSHighResolutionCapable": True,
		"NSSupportsAutomaticGraphicsSwitching": True,
		"LSEnvironment": {
			"QT_QUICK_CONTROLS_STYLE": "macOS",
		},
	}
	if icns_path.is_file():
		plist["CFBundleIconFile"] = icns_name
	plist_path = app_bundle / "Contents" / "Info.plist"
	plist_path.parent.mkdir(parents=True, exist_ok=True)
	plist_path.write_bytes(plistlib.dumps(plist))


def _install_icons(prefix: Path) -> tuple[Path, list[Path]]:
	"""Copy hicolor icons into the prefix and user icon theme."""
	share_icons = prefix / "share" / "icons" / "hicolor"
	user_icons = Path.home() / ".local" / "share" / "icons" / "hicolor"
	sizes = available_icon_sizes() or [256]
	installed_256 = share_icons / "256x256" / "apps" / "srxy.png"
	user_icon_paths: list[Path] = []
	for size in sizes:
		source = app_icon_path(size=size)
		for root in (share_icons, user_icons):
			target_dir = root / f"{size}x{size}" / "apps"
			target_dir.mkdir(parents=True, exist_ok=True)
			target = target_dir / "srxy.png"
			shutil.copy2(source, target)
			if root == user_icons:
				user_icon_paths.append(target)
	master = app_icon_path()
	for root in (share_icons, user_icons):
		target_dir = root / "512x512" / "apps"
		target_dir.mkdir(parents=True, exist_ok=True)
		target = target_dir / "srxy.png"
		shutil.copy2(master, target)
		if root == user_icons:
			user_icon_paths.append(target)
	icon_for_desktop = installed_256 if installed_256.is_file() else app_icon_path(size=256)
	return icon_for_desktop, user_icon_paths


def _write_desktop_entry(prefix: Path):
	apps = Path.home() / ".local" / "share" / "applications"
	apps.mkdir(parents=True, exist_ok=True)
	desktop = apps / "srxy.desktop"
	exec_path = prefix / "bin" / "srxy"
	desktop.write_text(
		"\n".join(
			[
				"[Desktop Entry]",
				"Type=Application",
				"Name=srxy",
				"Comment=Find files by what you mean",
				f"Exec={exec_path}",
				"Icon=srxy",
				"Terminal=false",
				"Categories=Utility;FileTools;",
				"StartupNotify=true",
				"",
			]
		),
		encoding="utf-8",
	)


def _is_linux() -> bool:
	return platform.system().lower() == "linux"


def _is_windows() -> bool:
	return platform.system().lower() == "windows"


def package_extras_for_host(*, install_semantic: bool) -> list[str]:
	"""Extras required for a prefix install on the current host OS.

	``pywin32`` is a core Windows dependency (platform marker), so there is no
	``[windows]`` extra to add here.
	"""
	if install_semantic:
		return ["semantic"]
	return []


def _venv_python(venv: Path) -> Path:
	if _is_windows():
		return venv / "Scripts" / "python.exe"
	return venv / "bin" / "python"


def _path_sep() -> str:
	return ";" if _is_windows() else ":"


def _resolve_uv(prefix: Path) -> Path:
	vendor_uv = prefix / "vendor" / "uv"
	for name in ("uv.exe", "uv"):
		candidate = vendor_uv / name
		if candidate.is_file():
			return candidate
	which = shutil.which("uv")
	if which:
		return Path(which)
	raise RuntimeError("uv is not available; vendor install failed")


def _package_version(venv: Path | None = None) -> str:
	if venv is not None:
		python = _venv_python(venv)
		if python.is_file():
			result = subprocess.run(  # noqa: S603
				[str(python), "-c", "from importlib.metadata import version; print(version('srxy'))"],
				capture_output=True,
				text=True,
				check=False,
			)
			if result.returncode == 0 and result.stdout.strip():
				return result.stdout.strip()
	try:
		return package_version("srxy")
	except Exception:
		return "unknown"


def _complete_phase(*, progress: ProgressCallback | None, label: str):
	if progress is not None:
		progress(1, 1, label)


def _persist_installer_language(prefix: Path, ui_language: str | None):
	"""Write installer UI language to prefix settings when no settings file exists yet."""
	if not ui_language:
		return
	from srxy.application.settings import set_language_setting
	from srxy.i18n import resolve_language

	prefix_settings = prefix / "settings.json"
	if prefix_settings.is_file():
		return

	code = resolve_language(ui_language)
	prior_home = os.environ.get("SRXY_HOME")
	os.environ["SRXY_HOME"] = str(prefix)
	try:
		set_language_setting(code)
	finally:
		if prior_home is None:
			os.environ.pop("SRXY_HOME", None)
		else:
			os.environ["SRXY_HOME"] = prior_home


def install_srxy(
	options: InstallOptions,
	*,
	status: StatusCallback | None = None,
	progress: ProgressCallback | None = None,
	task: TaskCallback | None = None,
	task_offset: int = 0,
	task_total: int | None = None,
	cancel_file: str | None = None,
) -> InstallManifest:
	"""Install srxy into ``options.prefix``.

	``task_offset`` / ``task_total`` let reinstall prepend an uninstall phase while
	keeping a single overall k/n counter.
	"""
	prefix = options.prefix.expanduser().resolve()
	prior_cancel_env = os.environ.get("SRXY_INSTALLER_CANCEL_FILE")
	if cancel_file:
		os.environ["SRXY_INSTALLER_CANCEL_FILE"] = cancel_file
	try:
		return _install_srxy_body(
			options,
			prefix=prefix,
			status=status,
			progress=progress,
			task=task,
			task_offset=task_offset,
			task_total=task_total,
			cancel_file=cancel_file,
		)
	finally:
		if prior_cancel_env is None:
			os.environ.pop("SRXY_INSTALLER_CANCEL_FILE", None)
		else:
			os.environ["SRXY_INSTALLER_CANCEL_FILE"] = prior_cancel_env


def _install_srxy_body(
	options: InstallOptions,
	*,
	prefix: Path,
	status: StatusCallback | None = None,
	progress: ProgressCallback | None = None,
	task: TaskCallback | None = None,
	task_offset: int = 0,
	task_total: int | None = None,
	cancel_file: str | None = None,
) -> InstallManifest:
	_validate_install_prefix(prefix, confirm_unsafe=options.confirm_unsafe)
	if looks_like_partial_srxy_prefix(prefix):
		_status(status, tr("installer.status.reclaiming_partial"))
		shutil.rmtree(prefix)
	elif is_srxy_prefix(prefix):
		_status(status, tr("installer.status.reinstalling"))
	prefix.mkdir(parents=True, exist_ok=True)
	(prefix / "logs").mkdir(parents=True, exist_ok=True)

	phases = plan_install_phases(options)
	overall_total = task_total if task_total is not None else len(phases)

	def emit_task(local_index: int, label: str):
		_raise_if_cancelled(cancel_file)
		overall_index = task_offset + local_index
		_status(status, label)
		_task(task, index=overall_index, total=overall_total, label=label)
		if progress is not None:
			progress(0, 0, label)

	# --- 1. uv ---
	emit_task(1, phases[0].label)
	install_uv(prefix, progress=progress, cancel_file=cancel_file)
	_complete_phase(progress=progress, label=phases[0].label)
	uv = _resolve_uv(prefix)

	# --- 2. venv ---
	emit_task(2, phases[1].label)
	venv = prefix / ".venv"
	_run([str(uv), "venv", "--clear", "--python", "3.12", str(venv)], cancel_file=cancel_file)
	_complete_phase(progress=progress, label=phases[1].label)

	env = os.environ.copy()
	env["VIRTUAL_ENV"] = str(venv)
	venv_bin = venv / "Scripts" if _is_windows() else venv / "bin"
	env["PATH"] = f"{venv_bin}{_path_sep()}{env.get('PATH', '')}"

	spec = (options.srxy_spec or "").strip() or resolve_srxy_install_spec()
	# semantic is optional; pywin32 is a core Windows dependency (no [windows] extra).
	extra_names = package_extras_for_host(install_semantic=options.install_semantic)
	if extra_names:
		spec = with_extras(spec, *extra_names)

	# --- 3. package ---
	package_label = tr("installer.status.installing_package", spec=spec)
	emit_task(3, package_label)
	_run_with_stdout_progress(
		[str(uv), "pip", "install", spec],
		env=env,
		progress=progress,
		cancel_file=cancel_file,
		heartbeat_label=package_label,
	)
	_complete_phase(progress=progress, label=package_label)

	probe = subprocess.run(  # noqa: S603
		[str(_venv_python(venv)), "-c", "import PySide6"],
		capture_output=True,
		text=True,
		check=False,
		env=env,
	)
	if probe.returncode != 0:
		raise RuntimeError(
			"Installed srxy is missing PySide6 (GUI). The installer must use a local "
			"wheel/source build that includes the desktop UI — not an older PyPI build.\n"
			f"{(probe.stderr or probe.stdout).strip()}"
		)

	# Keep the same PySide pin as packaging/macos offline builds. A floating
	# 6.11.x patch can change Quick Controls macOS chrome vs ``uv run`` / the
	# installer wizard the user just saw.
	if platform.system().lower() == "darwin":
		_run_with_stdout_progress(
			[str(uv), "pip", "install", "PySide6==6.11.1"],
			env=env,
			progress=progress,
			cancel_file=cancel_file,
			heartbeat_label=package_label,
		)

	phase_by_key = {phase.key: (i + 1, phase) for i, phase in enumerate(phases)}

	if "cuda_torch" in phase_by_key:
		local_index, phase = phase_by_key["cuda_torch"]
		emit_task(local_index, phase.label)

		def cuda_run(cmd: list[str], env: dict[str, str] | None = None):
			_run_with_stdout_progress(
				cmd,
				env=env,
				progress=progress,
				cancel_file=cancel_file,
				heartbeat_label=phase.label,
			)

		ensure_windows_cuda_torch(
			uv=uv,
			python=_venv_python(venv),
			env=env,
			run=cuda_run,
		)
		_complete_phase(progress=progress, label=phase.label)

	vendor_tesseract = False
	vendor_ffmpeg = False
	if options.download_tesseract:
		local_index, phase = phase_by_key["tesseract"]
		emit_task(local_index, phase.label)
		install_tesseract(prefix, progress=progress, tessdata_langs=options.tessdata_langs or None)
		_complete_phase(progress=progress, label=phase.label)
		vendor_tesseract = True
	if options.download_ffmpeg:
		local_index, phase = phase_by_key["ffmpeg"]
		emit_task(local_index, phase.label)
		install_ffmpeg(prefix, progress=progress)
		_complete_phase(progress=progress, label=phase.label)
		vendor_ffmpeg = True

	models_prefetched = False
	if options.install_semantic and options.prefetch_models:
		local_index, phase = phase_by_key["models"]
		emit_task(local_index, phase.label)
		env["SRXY_HOME"] = str(prefix)
		env["SRXY_AUTO_DOWNLOAD"] = "1"
		_run_with_progress(
			[
				str(_venv_python(venv)),
				"-m",
				"srxy.adapters.outbound.models.model_store",
				"all",
				"--progress",
			],
			env=env,
			progress=progress,
			cancel_file=cancel_file,
		)
		_complete_phase(progress=progress, label=phase.label)
		models_prefetched = True

	local_index, phase = phase_by_key["launcher"]
	emit_task(local_index, phase.label)
	write_launcher(prefix)
	user_icon_paths: list[Path] = []
	if _is_linux():
		_, user_icon_paths = _install_icons(prefix)
		_write_desktop_entry(prefix)
	_complete_phase(progress=progress, label=phase.label)

	path_rc = ""
	if options.add_to_path:
		from srxy.adapters.inbound.installer.path_setup import ensure_path_block

		local_index, phase = phase_by_key["path"]
		emit_task(local_index, phase.label)
		rc = ensure_path_block(prefix / "bin")
		path_rc = str(rc)
		_status(status, tr("installer.status.path_updated", rc=str(rc)))
		_complete_phase(progress=progress, label=phase.label)

	meta = load_installer_meta()
	manifest = InstallManifest(
		version=_package_version(venv),
		prefix=str(prefix),
		installed_at=utc_now_iso(),
		semantic=options.install_semantic,
		models_prefetched=models_prefetched,
		vendor_tesseract=vendor_tesseract,
		vendor_ffmpeg=vendor_ffmpeg,
		path_rc=path_rc,
		installer_version=meta.installer_version,
		privacy_ack_version=PRIVACY_NOTICE_VERSION,
		user_icons=[str(path) for path in user_icon_paths],
		extra={
			"python": sys.version.split()[0],
			"marker": MANIFEST_NAME,
			"srxy_spec": spec,
		},
	)
	write_manifest(prefix, manifest)
	_persist_installer_language(prefix, options.ui_language)
	_status(status, tr("installer.status.install_complete"))
	return manifest


__all__ = [
	"InstallCancelledError",
	"InstallOptions",
	"InstallPhase",
	"TaskCallback",
	"install_srxy",
	"plan_install_phases",
	"write_launcher",
]
