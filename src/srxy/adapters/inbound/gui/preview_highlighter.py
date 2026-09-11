"""Native ``QSyntaxHighlighter`` for the GUI file preview pane."""

from __future__ import annotations

from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QTextDocument

from srxy.adapters.inbound.gui.preview import PREVIEW_PALETTES, PreviewPalette, segments_for_line


class PreviewHighlighter(QSyntaxHighlighter):
	"""Apply syntax colours and find/hit overlays to a plain-text preview document."""

	def __init__(self, document: QTextDocument):
		super().__init__(document)
		self._suffix = ""
		self._theme = "light"
		self._hits: dict[int, list[tuple[int, int]]] = {}
		self._finds: dict[int, list[tuple[int, int]]] = {}
		self._currents: dict[int, list[tuple[int, int]]] = {}
		self._formats: dict[str, QTextCharFormat] = {}
		self._rebuild_formats()

	def set_context(self, *, suffix: str, theme: str):
		"""Update file suffix / theme; callers should ``rehighlight()`` after."""
		self._suffix = suffix.lower()
		self._theme = theme if theme in PREVIEW_PALETTES else "light"
		self._rebuild_formats()

	def set_overlays(
		self,
		hits: dict[int, list[tuple[int, int]]] | None = None,
		finds: dict[int, list[tuple[int, int]]] | None = None,
		current: dict[int, list[tuple[int, int]]] | None = None,
	):
		"""Replace overlay maps (1-based line numbers → raw-line spans)."""
		self._hits = hits or {}
		self._finds = finds or {}
		self._currents = current or {}

	def overlay_line_numbers(self) -> set[int]:
		"""Return 1-based line numbers that currently carry any overlay."""
		return set(self._hits) | set(self._finds) | set(self._currents)

	def highlightBlock(self, text: str):  # noqa: N802 — Qt override
		line_number = self.currentBlock().blockNumber() + 1
		for start, end, kind in segments_for_line(text, self._suffix):
			fmt = self._formats.get(kind) if kind else None
			if fmt is not None and start < end:
				self.setFormat(start, end - start, fmt)
		overlays = self._merge_overlays(
			self._hits.get(line_number, []),
			self._finds.get(line_number, []),
			self._currents.get(line_number, []),
		)
		for start, end, background_key in overlays:
			base = QTextCharFormat(self.format(start))
			base.setBackground(QColor(self._palette_colour(background_key)))
			self.setFormat(start, end - start, base)

	def _rebuild_formats(self):
		palette = self._palette()
		self._formats = {
			"keyword": self._foreground(palette.keyword),
			"string": self._foreground(palette.string),
			"comment": self._foreground(palette.comment),
			"heading": self._foreground(palette.heading),
		}

	def _palette(self) -> PreviewPalette:
		return PREVIEW_PALETTES.get(self._theme, PREVIEW_PALETTES["light"])

	def _palette_colour(self, key: str) -> str:
		palette = self._palette()
		return {
			"hit": palette.hit_background,
			"find": palette.find_background,
			"current": palette.find_current_background,
		}[key]

	@staticmethod
	def _foreground(colour: str) -> QTextCharFormat:
		fmt = QTextCharFormat()
		fmt.setForeground(QColor(colour))
		return fmt

	@staticmethod
	def _merge_overlays(
		hits: list[tuple[int, int]],
		finds: list[tuple[int, int]],
		currents: list[tuple[int, int]],
	) -> list[tuple[int, int, str]]:
		"""Merge hit/find/current ranges into non-overlapping background spans.

		Precedence: current > find > hit.
		"""
		points: set[int] = set()
		for start, end in (*hits, *finds, *currents):
			if start < end:
				points.add(start)
				points.add(end)
		ordered = sorted(points)
		overlays: list[tuple[int, int, str]] = []
		for index in range(len(ordered) - 1):
			start, end = ordered[index], ordered[index + 1]
			if start == end:
				continue
			if _covers(currents, start, end):
				key = "current"
			elif _covers(finds, start, end):
				key = "find"
			elif _covers(hits, start, end):
				key = "hit"
			else:
				continue
			if overlays and overlays[-1][1] == start and overlays[-1][2] == key:
				overlays[-1] = (overlays[-1][0], end, key)
			else:
				overlays.append((start, end, key))
		return overlays


def _covers(ranges: list[tuple[int, int]], start: int, end: int) -> bool:
	for range_start, range_end in ranges:
		if range_start <= start and range_end >= end:
			return True
	return False
