#!/usr/bin/env bash
# Regenerate docs/images/tui.{svg,png} for README and docs/tui.md.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=scripts/quality/internal/lib.sh
source "$ROOT/scripts/quality/internal/lib.sh"

lib_require_venv
lib_activate_venv
cd "$ROOT"

mkdir -p docs/images

PNG_MAX_WIDTH=880

python <<'PY'
import asyncio
import re
from pathlib import Path
from unittest.mock import AsyncMock, patch

from srxy.cli import build_parser
from srxy.models import FileSearchResult, LineMatch
from srxy.tui.app import SrxyApp
from textual.widgets import DataTable

TERMINAL_SIZE = (120, 32)
DOCS_THEME = "textual-light"
SCREENSHOT_CSS = """
#search-button {
    background: #0178d4;
    color: #ffffff;
}
#options-bar Checkbox.-on {
    background: #0178d4;
    color: #ffffff;
}
"""
PRIMARY_BLUE = "#0178d4"
SEARCH_TEXT_WHITE = "#ffffff"
MUTED_PRIMARY = "#3a3a3a"

def doc_path(relative: str) -> Path:
    return Path("file_search") / relative


results = [
    FileSearchResult(
        path=doc_path("ocr.pdf"),
        score=0.93,
        breakdown={"ocr": 0.93},
        lines=[
            LineMatch(
                line_number=1,
                text="Total revenue increased 12% year over year",
                score=0.93,
                location_kind="ocr",
            )
        ],
    ),
    FileSearchResult(
        path=doc_path("notes.txt"),
        score=0.91,
        breakdown={"content": 0.91},
        lines=[
            LineMatch(
                line_number=4,
                text="The axolotl is a paedomorphic salamander native to lakes around",
                score=0.91,
                location_kind="line",
            )
        ],
    ),
    FileSearchResult(
        path=doc_path("portrait.jpg"),
        score=0.82,
        breakdown={"semantic_image": 0.82},
        lines=[
            LineMatch(
                line_number=1,
                text="person",
                score=0.82,
                location_kind="semantic_image",
            )
        ],
    ),
    FileSearchResult(
        path=doc_path("speech.wav"),
        score=0.78,
        breakdown={"transcript": 0.78},
        lines=[
            LineMatch(
                line_number=1,
                text="thank you very much",
                score=0.78,
                location_kind="transcript",
            )
        ],
    ),
]
args = build_parser().parse_args(
    [
        "revenue|axolotl|thank you",
        "file_search",
        "--semantic-all",
        "--content-only",
    ]
)
app = SrxyApp(args, auto_start=True)
app.theme = DOCS_THEME


def boost_screenshot_contrast(svg: str) -> str:
    """Textual SVG export mutes $primary; restore readable primary blue for docs."""
    boosted = svg.replace(f'fill="{MUTED_PRIMARY}"', f'fill="{PRIMARY_BLUE}"')
    return re.sub(
        r'(<text class="[^"]+"[^>]*)(>[^<]*&#160;Search&#160;</text>)',
        rf'\1 fill="{SEARCH_TEXT_WHITE}"\2',
        boosted,
        count=1,
    )


async def run():
    with (
        patch("srxy.tui.app.run_tui_preflight", new=AsyncMock(return_value=None)),
        patch("srxy.tui.app.search_uses_subprocess", return_value=False),
        patch("srxy.tui.app.execute_search", return_value=(results, [])),
    ):
        async with app.run_test(size=TERMINAL_SIZE) as pilot:
            app.stylesheet.add_source(SCREENSHOT_CSS)
            for _ in range(80):
                await pilot.pause(delay=0.05)
                if app.query_one("#results-table", DataTable).row_count >= len(results):
                    break
            svg = boost_screenshot_contrast(app.export_screenshot(title="srxy"))
            Path("docs/images/tui.svg").write_text(svg, encoding="utf-8")


asyncio.run(run())
PY

if ! command -v rsvg-convert >/dev/null 2>&1; then
	echo "rsvg-convert not found; kept docs/images/tui.svg only" >&2
	exit 0
fi

read -r SVG_WIDTH SVG_HEIGHT < <(
	python <<'PY'
import re
from pathlib import Path

svg = Path("docs/images/tui.svg").read_text(encoding="utf-8")
match = re.search(r'viewBox="0 0 ([0-9.]+) ([0-9.]+)"', svg)
if not match:
    raise SystemExit("could not parse SVG viewBox")
print(match.group(1), match.group(2))
PY
)

PNG_WIDTH="${PNG_MAX_WIDTH}"
PNG_HEIGHT="$(python -c "print(round(${PNG_WIDTH} * ${SVG_HEIGHT} / ${SVG_WIDTH}))")"
rsvg-convert -w "${PNG_WIDTH}" -h "${PNG_HEIGHT}" docs/images/tui.svg -o docs/images/tui.png
echo "Wrote docs/images/tui.svg and docs/images/tui.png (${PNG_WIDTH}x${PNG_HEIGHT})"
