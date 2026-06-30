from __future__ import annotations

import argparse
import asyncio
import json
import multiprocessing
import os
import sys
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any, TextIO

from srxy.cli import apply_args_to_env, execute_search
from srxy.models import FileSearchResult, LineMatch, SkippedFile


_worker_stdin: TextIO | None = None


def _bootstrap_worker_env():
	os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
	os.environ.setdefault("OMP_NUM_THREADS", "1")
	os.environ.setdefault("TQDM_DISABLE", "1")
	os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
	os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
	os.environ.setdefault("JOBLIB_MULTIPROCESSING", "0")


def build_worker_env() -> dict[str, str]:
	# Inherit the full parent environment so Windows subprocesses can load
	# Winsock (_overlapped/asyncio) and locate system DLLs (SystemRoot, etc.).
	env = dict(os.environ)
	_bootstrap_worker_env()
	for key in (
		"TOKENIZERS_PARALLELISM",
		"OMP_NUM_THREADS",
		"TQDM_DISABLE",
		"HF_HUB_DISABLE_PROGRESS_BARS",
		"TRANSFORMERS_VERBOSITY",
		"JOBLIB_MULTIPROCESSING",
	):
		env[key] = os.environ[key]
	return env


def _detach_worker_stdin():
	global _worker_stdin
	devnull_fd = os.open(os.devnull, os.O_RDONLY)
	try:
		os.dup2(devnull_fd, 0)
	finally:
		os.close(devnull_fd)
	_worker_stdin = open(os.devnull)
	sys.stdin = _worker_stdin


def _close_worker_stdin():
	global _worker_stdin
	if _worker_stdin is not None:
		_worker_stdin.close()
		_worker_stdin = None


def search_uses_subprocess(args: argparse.Namespace) -> bool:
	"""Heavy search modes run in a child interpreter; avoid mp.Queue inside Textual."""
	return bool(args.semantic_image or args.semantic or args.semantic_all or args.ocr or args.transcribe)


def args_to_payload(args: argparse.Namespace) -> dict[str, Any]:
	payload: dict[str, Any] = {}
	for key, value in vars(args).items():
		if isinstance(value, Path):
			payload[key] = str(value)
		else:
			payload[key] = value
	return payload


def file_result_to_dict(result: FileSearchResult) -> dict[str, Any]:
	return {
		"path": str(result.path),
		"score": result.score,
		"breakdown": result.breakdown,
		"term_surfaces": result.term_surfaces,
		"lines": [
			{
				"line_number": line.line_number,
				"text": line.text,
				"score": line.score,
				"location_kind": line.location_kind,
				"matched_term": line.matched_term,
			}
			for line in result.lines
		],
	}


def file_result_from_dict(data: dict[str, Any]) -> FileSearchResult:
	return FileSearchResult(
		path=Path(data["path"]),
		score=data["score"],
		breakdown=data.get("breakdown", {}),
		lines=[LineMatch(**line) for line in data.get("lines", [])],
		term_surfaces=data.get("term_surfaces", {}),
	)


def skipped_file_from_dict(data: dict[str, Any]) -> SkippedFile:
	return SkippedFile(
		path=Path(data["path"]),
		size_bytes=data["size_bytes"],
		reason=data.get("reason", "oversized"),
	)


def _emit_event(event: dict[str, Any]):
	sys.stdout.write(json.dumps(event) + "\n")
	sys.stdout.flush()


def run_worker_main():
	_bootstrap_worker_env()
	if sys.platform != "win32":
		try:
			multiprocessing.set_start_method("fork", force=True)
		except (RuntimeError, ValueError):
			pass
	try:
		line = sys.stdin.readline()
		if not line:
			_emit_event({"type": "error", "message": "missing search arguments"})
			_emit_event({"type": "done"})
			return

		args = argparse.Namespace(**json.loads(line))
		_detach_worker_stdin()
		apply_args_to_env(args)
		skipped_files: list[SkippedFile] = []

		def on_progress(current: int, total: int):
			_emit_event({"type": "progress", "current": current, "total": total})

		def on_activity(message: str | None):
			_emit_event({"type": "activity", "message": message})

		def on_result(result: FileSearchResult):
			_emit_event({"type": "result", "result": file_result_to_dict(result)})

		try:
			results, skipped_files = execute_search(
				args,
				skipped_files=skipped_files,
				on_progress=on_progress,
				on_activity=on_activity,
				on_result=on_result,
			)
		except Exception as error:
			_emit_event({"type": "error", "message": str(error)})
			_emit_event({"type": "done"})
			return

		_emit_event(
			{
				"type": "finished",
				"results": [file_result_to_dict(result) for result in results],
				"skipped_files": [
					{
						"path": str(skipped.path),
						"size_bytes": skipped.size_bytes,
						"reason": skipped.reason,
					}
					for skipped in skipped_files
				],
			}
		)
		_emit_event({"type": "done"})
	finally:
		_close_worker_stdin()


async def iter_subprocess_search_events(
	args: argparse.Namespace,
	*,
	cancel_check: Callable[[], bool] | None = None,
) -> AsyncIterator[dict[str, Any]]:
	env = build_worker_env()

	process = await asyncio.create_subprocess_exec(
		sys.executable,
		"-m",
		"srxy.tui.search_worker",
		stdin=asyncio.subprocess.PIPE,
		stdout=asyncio.subprocess.PIPE,
		stderr=asyncio.subprocess.PIPE,
		env=env,
		start_new_session=True,
	)
	if process.stdin is None or process.stdout is None:
		raise RuntimeError("search worker subprocess missing stdio pipes")

	process.stdin.write((json.dumps(args_to_payload(args)) + "\n").encode())
	await process.stdin.drain()
	process.stdin.close()

	try:
		while True:
			if cancel_check and cancel_check():
				process.terminate()
				return

			line = await process.stdout.readline()
			if not line:
				stderr = b""
				if process.stderr is not None:
					stderr = await process.stderr.read()
				if stderr:
					message = stderr.decode(errors="replace").strip().splitlines()[-1]
					yield {"type": "error", "message": message or "search worker failed"}
				else:
					yield {"type": "error", "message": "search worker exited unexpectedly"}
				break

			text = line.decode().strip()
			if not text:
				continue

			event = json.loads(text)
			if event.get("type") == "done":
				break
			yield event
	finally:
		if process.returncode is None:
			process.terminate()
		await process.wait()


if __name__ == "__main__":
	run_worker_main()


__all__ = [
	"args_to_payload",
	"build_worker_env",
	"file_result_from_dict",
	"file_result_to_dict",
	"iter_subprocess_search_events",
	"run_worker_main",
	"search_uses_subprocess",
	"skipped_file_from_dict",
]
