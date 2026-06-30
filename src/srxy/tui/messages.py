from __future__ import annotations

from textual.message import Message

from srxy.models import FileSearchResult, SkippedFile
from srxy.progress import ActivityUpdate


class ProgressUpdated(Message):
	def __init__(self, current: int, total: int):
		self.current = current
		self.total = total
		super().__init__()


class ActivityChanged(Message):
	def __init__(self, activity: ActivityUpdate | None):
		self.activity = activity
		super().__init__()


class ResultFound(Message):
	def __init__(self, result: FileSearchResult):
		self.result = result
		super().__init__()


class SearchFinished(Message):
	def __init__(self, results: list[FileSearchResult], skipped_files: list[SkippedFile]):
		self.results = results
		self.skipped_files = skipped_files
		super().__init__()


class SearchError(Message):
	def __init__(self, message: str):
		self.error = message
		super().__init__()


__all__ = [
	"ActivityChanged",
	"ProgressUpdated",
	"ResultFound",
	"SearchError",
	"SearchFinished",
]
