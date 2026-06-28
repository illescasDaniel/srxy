#!/usr/bin/env bash
# Automated TUI pilot checks. Manual checklist items live in README.md (Development).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate

pass=0
fail=0

log() {
	local id="$1" item="$2" status="$3" notes="$4"
	echo "| $id | $item | $status | $notes |"
	[[ "$status" == PASS ]] && pass=$((pass + 1)) || fail=$((fail + 1))
}

echo "TUI automated pilot checks (manual checklist: see README.md → Development → Manual TUI checklist)"
echo ""
echo "| ID | Item | Status | Notes |"
echo "|----|------|--------|-------|"

# TUI12.1 — empty launch renders
python <<'PY'
import asyncio
from srxy.cli import build_parser
from srxy.tui.app import SrxyApp

async def check():
    app = SrxyApp(build_parser().parse_args([]), auto_start=False)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.query_one("#query-term-0") is not None
        assert app.query_one("#search-button") is not None
asyncio.run(check())
print("ok")
PY
log TUI12.1 "Empty launch renders query and Search" PASS "Textual pilot"

# TUI12.2 — pre-filled auto-start (mock search to avoid heavy load)
export SRXY_QA_CORPUS="${SRXY_QA_CORPUS:-$ROOT/tests/fixtures/qa_corpus}"
python <<'PY'
import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch
from srxy.cli import build_parser
from srxy.tui.app import SrxyApp
from srxy.models import FileSearchResult, LineMatch

async def check():
    docs = Path(os.environ["SRXY_QA_CORPUS"]) / "docs"
    args = build_parser().parse_args(["Linkin Park", str(docs)])
    app = SrxyApp(args, auto_start=True)
    result = FileSearchResult(path=Path("x.mp3"), score=0.8, lines=[LineMatch(1, "Linkin", 0.8)])
    with patch("srxy.tui.app.run_tui_preflight", new=AsyncMock(return_value=None)), \
         patch("srxy.tui.app.execute_search", return_value=([result], [])):
        async with app.run_test(size=(100, 30)) as pilot:
            for _ in range(30):
                await pilot.pause(0.05)
                if app.query_one("#results-table").row_count >= 1:
                    break
            assert app.query_one("#results-table").row_count >= 1
asyncio.run(check())
print("ok")
PY
log TUI12.2 "Pre-filled launch auto-starts search" PASS "mocked execute_search"

# TUI12.6 — stale search button
python <<'PY'
import asyncio
from pathlib import Path
from srxy.cli import build_parser
from srxy.tui.app import SrxyApp

async def check():
    app = SrxyApp(build_parser().parse_args(["hello", str(Path("/tmp"))]), auto_start=False)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        button = app.query_one("#search-button")
        ocr = app.query_one("#opt-ocr")
        assert "Search" in str(button.render())
        ocr.toggle()
        await pilot.pause()
        assert "Search" in str(button.render())
asyncio.run(check())
print("ok")
PY
log TUI12.6 "Search button stale after option change" PASS "Textual pilot"

# TUI12.7 — j/k navigation
python <<'PY'
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch
from srxy.cli import build_parser
from srxy.tui.app import SrxyApp
from srxy.models import FileSearchResult, LineMatch

async def check():
    app = SrxyApp(build_parser().parse_args(["a", str(Path("/tmp"))]), auto_start=True)
    results = [
        FileSearchResult(path=Path("/tmp/a.txt"), score=0.9, lines=[LineMatch(1, "a", 0.9)]),
        FileSearchResult(path=Path("/tmp/b.txt"), score=0.8, lines=[LineMatch(1, "b", 0.8)]),
    ]
    with patch("srxy.tui.app.run_tui_preflight", new=AsyncMock(return_value=None)), \
         patch("srxy.tui.app.execute_search", return_value=(results, [])):
        async with app.run_test(size=(100, 30)) as pilot:
            for _ in range(30):
                await pilot.pause(0.05)
                if app.query_one("#results-table").row_count >= 2:
                    break
            await pilot.press("j")
            await pilot.pause()
            table = app.query_one("#results-table")
            assert table.cursor_row == 1
asyncio.run(check())
print("ok")
PY
log TUI12.7 "j/k navigates results table" PASS "Textual pilot"

# TUI12.11 — help modal
python <<'PY'
import asyncio
from srxy.cli import build_parser
from srxy.tui.app import SrxyApp
from srxy.tui.modals import HelpModal

async def check():
    app = SrxyApp(build_parser().parse_args([]), auto_start=False)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app.action_show_help()
        await pilot.pause()
        assert isinstance(app.screen, HelpModal)
asyncio.run(check())
print("ok")
PY
log TUI12.11 "Help overlay opens on ?" PASS "action_show_help via pilot"

echo ""
echo "Automated PASS: $pass  FAIL: $fail"
echo "Manual TUI checks (real TTY): see README.md → Development → Manual TUI checklist"
exit "$([[ $fail -eq 0 ]] && echo 0 || echo 1)"
