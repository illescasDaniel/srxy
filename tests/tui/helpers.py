from __future__ import annotations

import html
import re
from collections.abc import Iterable

from textual.app import App


_BORDER_GLYPHS = frozenset("▄▀─━▐▌")


def extract_svg_visible_text(svg: str) -> list[str]:
	"""Return human-readable strings from a Textual SVG screenshot."""
	texts: list[str] = []
	for match in re.finditer(r"<text[^>]*>([^<]*)</text>", svg):
		text = html.unescape(match.group(1)).strip()
		if not text:
			continue
		if all(char in _BORDER_GLYPHS or char.isspace() for char in text):
			continue
		texts.append(text)
	return texts


def normalized_svg_text(svg: str) -> str:
	"""Flatten visible SVG text for substring assertions."""
	return " ".join(extract_svg_visible_text(svg)).replace("\xa0", " ")


def assert_labels_visible(svg: str, labels: Iterable[str]) -> None:
	"""Assert each label appears in the exported screenshot."""
	visible = normalized_svg_text(svg)
	missing = [label for label in labels if label not in visible]
	if missing:
		snippet = visible[:500] + ("…" if len(visible) > 500 else "")
		raise AssertionError(f"Missing labels in TUI screenshot: {missing}\nVisible text: {snippet!r}")


async def export_app_screenshot(app: App[int], *, size: tuple[int, int] = (100, 30)) -> str:
	"""Run the app headlessly and return an SVG screenshot."""
	async with app.run_test(size=size) as pilot:
		await pilot.pause()
		return app.export_screenshot(title="srxy-tui")
