from __future__ import annotations

import argparse
import json
import os
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from srxy.cli import build_parser
from srxy.models import FileSearchResult, LineMatch, SkippedFile
from srxy.tui.search_worker import (
	args_to_payload,
	build_worker_env,
	file_result_from_dict,
	file_result_to_dict,
	run_worker_main,
	search_uses_subprocess,
)


pytestmark = pytest.mark.unit


def _build_args(argv: list[str]) -> argparse.Namespace:
	return build_parser().parse_args(argv)


def test_given_semantic_image_flag_when_search_uses_subprocess_then_returns_true():
	# given
	args = _build_args(["person", ".", "--semantic-image"])

	# when / then
	assert search_uses_subprocess(args) is True


def test_given_ocr_flag_when_search_uses_subprocess_then_returns_true():
	# given
	args = _build_args(["transform", ".", "--ocr"])

	# when / then
	assert search_uses_subprocess(args) is True


def test_given_name_only_search_when_search_uses_subprocess_then_returns_false():
	# given
	args = _build_args(["person", "."])

	# when / then
	assert search_uses_subprocess(args) is False


def test_given_file_search_result_when_round_trip_dict_then_preserves_fields(tmp_path: Path):
	# given
	result = FileSearchResult(
		path=tmp_path / "photo.png",
		score=0.86,
		breakdown={"ocr": 0.86},
		lines=[LineMatch(line_number=1, text="revenue", score=0.9, location_kind="ocr")],
	)

	# when
	restored = file_result_from_dict(file_result_to_dict(result))

	# then
	assert restored == result


def test_given_worker_args_when_run_worker_main_then_emits_json_events(monkeypatch: pytest.MonkeyPatch):
	# given
	args = _build_args(["transform", ".", "--ocr", "--no-tui"])
	result = FileSearchResult(path=Path("doc.png"), score=0.5, lines=[])
	skipped = [SkippedFile(path=Path("big.png"), size_bytes=99)]
	stdout = StringIO()
	monkeypatch.setattr("sys.stdin", StringIO(json.dumps(args_to_payload(args)) + "\n"))
	monkeypatch.setattr("sys.stdout", stdout)
	monkeypatch.setattr(
		"srxy.tui.search_worker.execute_search",
		MagicMock(return_value=([result], skipped)),
	)

	# when
	run_worker_main()

	# then
	events = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
	assert events[0] == {
		"type": "finished",
		"results": [file_result_to_dict(result)],
		"skipped_files": [{"path": "big.png", "size_bytes": 99, "reason": "oversized"}],
	}
	assert events[-1] == {"type": "done"}


def test_given_parent_env_when_build_worker_env_then_inherits_platform_paths(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_SEMANTIC", "1")
	monkeypatch.setenv("CUSTOM_PARENT_ONLY", "keep-me")

	# when
	env = build_worker_env()

	# then
	assert env["SRXY_SEMANTIC"] == "1"
	assert env["CUSTOM_PARENT_ONLY"] == "keep-me"
	assert env["PATH"] == os.environ["PATH"]
	if os.name == "nt":
		system_root = env.get("SYSTEMROOT") or env.get("SystemRoot")
		assert system_root == os.environ.get("SYSTEMROOT") or os.environ.get("SystemRoot")


def test_given_worker_args_when_run_worker_main_then_sets_worker_env(
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	args = _build_args(["transform", ".", "--ocr", "--no-tui"])
	stdout = StringIO()
	for key in ("TQDM_DISABLE", "JOBLIB_MULTIPROCESSING"):
		monkeypatch.delenv(key, raising=False)
	monkeypatch.setattr("sys.stdin", StringIO(json.dumps(args_to_payload(args)) + "\n"))
	monkeypatch.setattr("sys.stdout", stdout)
	monkeypatch.setattr(
		"srxy.tui.search_worker.execute_search",
		MagicMock(return_value=([], [])),
	)

	# when
	run_worker_main()

	# then
	assert os.environ["TQDM_DISABLE"] == "1"
	assert os.environ["JOBLIB_MULTIPROCESSING"] == "0"
