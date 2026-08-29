from __future__ import annotations

from pathlib import Path

import pytest
from tests.isolation import apply_isolated_cache_environment

from srxy.adapters.inbound.gui import capabilities


_GUI_ROOT = Path(__file__).resolve().parent


@pytest.fixture(autouse=True)
def isolated_gui_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	yield from apply_isolated_cache_environment(tmp_path, monkeypatch)


@pytest.fixture(autouse=True)
def _gui_no_gpu_probe(monkeypatch: pytest.MonkeyPatch):  # pyright: ignore[reportUnusedFunction]
	monkeypatch.setattr(
		"srxy.adapters.inbound.gui.capabilities._probe_has_gpu",
		lambda: False,
	)
	capabilities.probe_capabilities.cache_clear()
	yield
	capabilities.probe_capabilities.cache_clear()


def pytest_collection_modifyitems(items: list[pytest.Item]):
	mark = pytest.mark.xdist_group("gui")
	for item in items:
		try:
			item.path.resolve().relative_to(_GUI_ROOT)
		except ValueError:
			continue
		item.add_marker(mark)
