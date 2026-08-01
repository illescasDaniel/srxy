from __future__ import annotations

from pathlib import Path

import pytest


_GUI_ROOT = Path(__file__).resolve().parent


def pytest_collection_modifyitems(items: list[pytest.Item]):
	mark = pytest.mark.xdist_group("gui")
	for item in items:
		try:
			item.path.resolve().relative_to(_GUI_ROOT)
		except ValueError:
			continue
		item.add_marker(mark)
