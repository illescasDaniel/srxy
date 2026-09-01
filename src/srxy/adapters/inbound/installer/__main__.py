from __future__ import annotations

import argparse
import sys
import unicodedata
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from srxy.adapters.inbound.installer.privacy import PRIVACY_NOTICE_VERSION
from srxy.i18n import tr


def _print_version() -> int:
	try:
		print(version("srxy"))
	except PackageNotFoundError:
		print("srxy (unknown version)")
	return 0


def _progress_text(value: object) -> str:
	"""Normalize progress text for Inno ExecAndLogOutput (ASCII-safe).

	Inno Setup reads the engine subprocess stdout via a Windows ANSI pipe.
	Any non-ASCII byte sequence appears as diamond-question glyphs in the
	progress page.  Steps: (1) replace Unicode ellipsis U+2026 with three
	ASCII dots (it does not decompose via NFD); (2) NFD-decompose so accented
	letters split into base + combining mark (e.g. n + U+0303 tilde);
	(3) drop all combining marks (category Mn) so only base letters survive;
	(4) replace any remaining non-ASCII codepoints with '?'.

	Result: "Anadiendo..." from "Anyadiendo..." (ñ -> n, ... stays ...).
	"""
	text = str(value).replace("\u2026", "...")
	nfd = unicodedata.normalize("NFD", text)
	# Drop combining marks (accents stripped off base letters).
	stripped = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
	return stripped.encode("ascii", "replace").decode("ascii")


def _configure_headless_stdio():
	"""Reconfigure stdout/stderr to UTF-8 for the headless engine path.

	On Windows the pipe encoding defaults to the OEM code page.  We force
	UTF-8 here so the log file receives full Unicode, while _progress_text
	already produces ASCII for the Inno progress-bar wire protocol.
	"""
	for stream in (sys.stdout, sys.stderr):
		reconfigure = getattr(stream, "reconfigure", None)
		if callable(reconfigure):
			try:
				reconfigure(encoding="utf-8", errors="replace")
			except (OSError, ValueError, AttributeError):
				pass


def _emit(kind: str, *parts: object):
	"""Write a machine-readable progress line to stdout (Inno / scripts)."""
	payload = "\t".join(_progress_text(part) for part in parts)
	sys.stdout.write(f"{kind}\t{payload}\n")
	sys.stdout.flush()


def _status_cb(message: str):
	_emit("STATUS", message)


def _progress_cb(done: float | int, total: float | int, label: str):
	_emit("PROGRESS", done, total, label)


def _task_cb(index: int, total: int, label: str):
	_emit("TASK", index, total, label)


def _build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(prog="srxy-installer", description="Install or uninstall srxy.")
	parser.add_argument("--version", action="store_true", help="Print srxy version and exit.")
	parser.add_argument(
		"--install",
		action="store_true",
		help="Run a headless install/update into --prefix (no GUI).",
	)
	parser.add_argument(
		"--reinstall",
		action="store_true",
		help="Headless wipe + fresh install into --prefix.",
	)
	parser.add_argument(
		"--uninstall",
		action="store_true",
		help="Headless uninstall of --prefix.",
	)
	parser.add_argument("--prefix", type=str, default="", help="Install prefix directory.")
	parser.add_argument("--tesseract", action="store_true", help="Vendor Tesseract OCR.")
	parser.add_argument(
		"--tessdata-langs",
		type=str,
		default="",
		help="Comma-separated tessdata language codes (always includes eng,osd).",
	)
	parser.add_argument("--ffmpeg", action="store_true", help="Vendor ffmpeg.")
	parser.add_argument("--semantic", action="store_true", help="Install [semantic] extras.")
	parser.add_argument(
		"--prefetch-models",
		action="store_true",
		help="Prefetch Hugging Face models (requires --semantic).",
	)
	parser.add_argument(
		"--add-path",
		action=argparse.BooleanOptionalAction,
		default=True,
		help="Add prefix bin/ to PATH (default: true).",
	)
	parser.add_argument(
		"--confirm-unsafe",
		action="store_true",
		help="Allow install/uninstall of prefixes that need confirmation.",
	)
	parser.add_argument(
		"--privacy-ack",
		type=str,
		default="",
		help=f"Privacy notice version acknowledged (expected: {PRIVACY_NOTICE_VERSION}).",
	)
	parser.add_argument(
		"--srxy-spec",
		type=str,
		default="",
		help="Override package spec / wheel path for install.",
	)
	parser.add_argument(
		"--language",
		type=str,
		default="",
		help="UI language for progress messages (en|es). Defaults to system/settings.",
	)
	parser.add_argument(
		"--cancel-file",
		type=str,
		default="",
		help="Path watched for cooperative install cancellation.",
	)
	parser.add_argument(
		"--remove-cache",
		action=argparse.BooleanOptionalAction,
		default=True,
		help="During uninstall, remove srxy cache data (default: true).",
	)
	parser.add_argument(
		"--remove-settings",
		action=argparse.BooleanOptionalAction,
		default=True,
		help="During uninstall, remove persisted settings (default: true).",
	)
	parser.add_argument(
		"--remove-models",
		action=argparse.BooleanOptionalAction,
		default=True,
		help="During uninstall, remove downloaded AI models (default: true).",
	)
	return parser


def _require_privacy_ack(ack: str):
	text = (ack or "").strip()
	if text != PRIVACY_NOTICE_VERSION:
		raise RuntimeError(
			f"privacy acknowledgment required: pass --privacy-ack {PRIVACY_NOTICE_VERSION} (got {text!r})"
		)


def _run_headless(args: argparse.Namespace) -> int:
	from srxy.adapters.inbound.installer.install import InstallOptions, install_srxy, plan_install_phases
	from srxy.adapters.inbound.installer.uninstall import uninstall_prefix
	from srxy.application.install_paths import default_install_prefix

	actions = [bool(args.install), bool(args.reinstall), bool(args.uninstall)]
	if sum(actions) != 1:
		raise RuntimeError("specify exactly one of --install, --reinstall, or --uninstall")

	prefix_raw = (args.prefix or "").strip()
	prefix = Path(prefix_raw).expanduser() if prefix_raw else default_install_prefix()
	cancel_file = (args.cancel_file or "").strip() or None

	if args.uninstall:
		_status_cb(tr("installer.status.removing_app"))
		_task_cb(1, 2, tr("installer.status.removing_app"))
		_progress_cb(0, 0, tr("installer.status.removing_app"))
		uninstall_prefix(
			prefix,
			status=_status_cb,
			confirm_unsafe=bool(args.confirm_unsafe),
			remove_cache=bool(args.remove_cache),
			remove_settings=bool(args.remove_settings),
			remove_models=bool(args.remove_models),
		)
		_task_cb(2, 2, tr("installer.status.uninstall_complete"))
		_progress_cb(1, 1, tr("installer.status.uninstall_complete"))
		_status_cb(tr("installer.status.uninstall_complete"))
		_emit("OK", "uninstall")
		return 0

	_require_privacy_ack(args.privacy_ack)
	from srxy.adapters.inbound.installer.tessdata_langs import default_tessdata_langs, normalize_tessdata_langs
	from srxy.i18n import get_language, resolve_language

	raw_langs = [part.strip() for part in str(args.tessdata_langs or "").split(",") if part.strip()]
	if raw_langs:
		tessdata_langs = normalize_tessdata_langs(raw_langs)
	else:
		tessdata_langs = default_tessdata_langs(get_language())
	ui_language: str | None = None
	lang_raw = (args.language or "").strip()
	if lang_raw:
		ui_language = resolve_language(lang_raw)
	options = InstallOptions(
		prefix=prefix,
		download_tesseract=bool(args.tesseract),
		download_ffmpeg=bool(args.ffmpeg),
		install_semantic=bool(args.semantic),
		prefetch_models=bool(args.semantic) and bool(args.prefetch_models),
		add_to_path=bool(args.add_path),
		srxy_spec=(args.srxy_spec or "").strip(),
		confirm_unsafe=bool(args.confirm_unsafe),
		tessdata_langs=tessdata_langs,
		ui_language=ui_language,
	)

	if args.reinstall:
		install_phases = plan_install_phases(options)
		overall_total = 1 + len(install_phases)
		_status_cb(tr("installer.status.removing_app"))
		_task_cb(1, overall_total, tr("installer.status.removing_app"))
		_progress_cb(0, 0, tr("installer.status.removing_app"))
		uninstall_prefix(
			prefix,
			status=_status_cb,
			confirm_unsafe=bool(args.confirm_unsafe),
			remove_cache=bool(args.remove_cache),
			remove_settings=bool(args.remove_settings),
			remove_models=bool(args.remove_models),
		)
		_progress_cb(1, 1, tr("installer.status.removing_app"))
		install_srxy(
			options,
			status=_status_cb,
			progress=_progress_cb,
			task=_task_cb,
			task_offset=1,
			task_total=overall_total,
			cancel_file=cancel_file,
		)
		_emit("OK", "reinstall")
		return 0

	install_srxy(
		options,
		status=_status_cb,
		progress=_progress_cb,
		task=_task_cb,
		cancel_file=cancel_file,
	)
	_emit("OK", "install")
	return 0


def main(argv: list[str] | None = None) -> int:
	parser = _build_parser()
	# parse_known_args keeps Qt-style unknown flags when launching the GUI.
	args, unknown = parser.parse_known_args(argv)
	if args.version:
		return _print_version()

	headless = bool(args.install or args.reinstall or args.uninstall)
	if headless:
		_configure_headless_stdio()
		# Reject leftover Qt flags so typos fail loudly.
		qt_like = [flag for flag in unknown if flag.startswith("-")]
		if qt_like:
			parser.error(f"unrecognized arguments: {' '.join(qt_like)}")
		lang = (args.language or "").strip()
		if lang:
			from srxy.i18n import resolve_language, set_language

			set_language(resolve_language(lang))
		from srxy.adapters.inbound.installer.cancel import InstallCancelledError

		try:
			return _run_headless(args)
		except InstallCancelledError:
			_emit("CANCEL", "install")
			return 1
		except Exception as exc:
			_emit("ERROR", str(exc))
			print(str(exc), file=sys.stderr)
			return 1

	from srxy.adapters.inbound.installer.app import run_installer

	return run_installer()


if __name__ == "__main__":
	sys.exit(main())
