from __future__ import annotations

from pathlib import Path

import pytest
from tests.isolation import apply_isolated_cache_environment


_TUI_ROOT = Path(__file__).resolve().parent


@pytest.fixture(autouse=True)
def isolated_tui_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	yield from apply_isolated_cache_environment(tmp_path, monkeypatch)


def pytest_collection_modifyitems(items: list[pytest.Item]):
	mark = pytest.mark.xdist_group("tui")
	for item in items:
		try:
			item.path.resolve().relative_to(_TUI_ROOT)
		except ValueError:
			continue
		item.add_marker(mark)
