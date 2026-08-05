from __future__ import annotations

import argparse
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from srxy.adapters.inbound.installer.privacy import PRIVACY_NOTICE_VERSION


def _print_version() -> int:
	try:
		print(version("srxy"))
	except PackageNotFoundError:
		print("srxy (unknown version)")
	return 0


def _emit(kind: str, *parts: object):
	"""Write a machine-readable progress line to stdout (Inno / scripts)."""
	payload = "\t".join(str(part) for part in parts)
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

	if args.uninstall:
		uninstall_prefix(
			prefix,
			status=_status_cb,
			confirm_unsafe=bool(args.confirm_unsafe),
		)
		_emit("OK", "uninstall")
		return 0

	_require_privacy_ack(args.privacy_ack)
	options = InstallOptions(
		prefix=prefix,
		download_tesseract=bool(args.tesseract),
		download_ffmpeg=bool(args.ffmpeg),
		install_semantic=bool(args.semantic),
		prefetch_models=bool(args.semantic) and bool(args.prefetch_models),
		add_to_path=bool(args.add_path),
		srxy_spec=(args.srxy_spec or "").strip(),
		confirm_unsafe=bool(args.confirm_unsafe),
	)

	if args.reinstall:
		install_phases = plan_install_phases(options)
		overall_total = 1 + len(install_phases)
		_status_cb("Removing existing installation")
		_task_cb(1, overall_total, "Removing existing installation")
		_progress_cb(0, 0, "Removing existing installation")
		uninstall_prefix(
			prefix,
			status=_status_cb,
			confirm_unsafe=bool(args.confirm_unsafe),
		)
		_progress_cb(1, 1, "Removing existing installation")
		install_srxy(
			options,
			status=_status_cb,
			progress=_progress_cb,
			task=_task_cb,
			task_offset=1,
			task_total=overall_total,
		)
		_emit("OK", "reinstall")
		return 0

	install_srxy(
		options,
		status=_status_cb,
		progress=_progress_cb,
		task=_task_cb,
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
		# Reject leftover Qt flags so typos fail loudly.
		qt_like = [flag for flag in unknown if flag.startswith("-")]
		if qt_like:
			parser.error(f"unrecognized arguments: {' '.join(qt_like)}")
		try:
			return _run_headless(args)
		except Exception as exc:
			_emit("ERROR", str(exc))
			print(str(exc), file=sys.stderr)
			return 1

	from srxy.adapters.inbound.installer.app import run_installer

	return run_installer()


if __name__ == "__main__":
	sys.exit(main())
