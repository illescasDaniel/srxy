from __future__ import annotations

import argparse
import json
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from srxy.cli import build_parser
from srxy.models import FileSearchResult, LineMatch, SkippedFile
from srxy.tui.search_worker import (
	args_to_payload,
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
