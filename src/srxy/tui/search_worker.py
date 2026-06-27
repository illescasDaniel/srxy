from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

from srxy.cli import apply_args_to_env, execute_search
from srxy.models import FileSearchResult, LineMatch, SkippedFile


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
		"lines": [
			{
				"line_number": line.line_number,
				"text": line.text,
				"score": line.score,
				"location_kind": line.location_kind,
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
	os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
	os.environ.setdefault("OMP_NUM_THREADS", "1")
	line = sys.stdin.readline()
	if not line:
		_emit_event({"type": "error", "message": "missing search arguments"})
		_emit_event({"type": "done"})
		return

	args = argparse.Namespace(**json.loads(line))
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


async def iter_subprocess_search_events(
	args: argparse.Namespace,
	*,
	cancel_check: Callable[[], bool] | None = None,
) -> AsyncIterator[dict[str, Any]]:
	env = os.environ.copy()
	env.setdefault("TOKENIZERS_PARALLELISM", "false")
	env.setdefault("OMP_NUM_THREADS", "1")

	process = await asyncio.create_subprocess_exec(
		sys.executable,
		"-m",
		"srxy.tui.search_worker",
		stdin=asyncio.subprocess.PIPE,
		stdout=asyncio.subprocess.PIPE,
		stderr=asyncio.subprocess.DEVNULL,
		env=env,
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
	"file_result_from_dict",
	"file_result_to_dict",
	"iter_subprocess_search_events",
	"run_worker_main",
	"search_uses_subprocess",
	"skipped_file_from_dict",
]
