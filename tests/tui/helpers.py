from __future__ import annotations

import html
import os
import re
from collections.abc import Iterable
from pathlib import Path

from textual.app import App


SNAPSHOTS_DIR = Path(__file__).parent / "snapshots"
UPDATE_TUI_SNAPSHOTS = os.environ.get("UPDATE_TUI_SNAPSHOTS") == "1"

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


def snapshot_svg_text(svg: str) -> str:
	"""Stable newline-separated visible text for snapshot files."""
	return "\n".join(extract_svg_visible_text(svg)).replace("\xa0", " ")


def assert_svg_snapshot(name: str, svg: str) -> None:
	"""Compare exported SVG visible text against a committed snapshot."""
	SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
	path = SNAPSHOTS_DIR / f"{name}.snap.txt"
	actual = snapshot_svg_text(svg)
	if UPDATE_TUI_SNAPSHOTS or not path.exists():
		path.write_text(f"{actual}\n", encoding="utf-8")
		return
	expected = path.read_text(encoding="utf-8").removesuffix("\n")
	if actual != expected:
		raise AssertionError(
			f"Snapshot {name!r} mismatch ({path}).\n"
			f"Re-run with UPDATE_TUI_SNAPSHOTS=1 to refresh.\n"
			f"--- expected ---\n{expected}\n--- actual ---\n{actual}"
		)


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
