from __future__ import annotations

from pathlib import Path

import pytest
from tests.isolation import apply_isolated_cache_environment


@pytest.fixture(autouse=True)
def isolated_cli_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# Force plain CLI for these tests even on a graphical session.
	yield from apply_isolated_cache_environment(tmp_path, monkeypatch, force_ci=True)
