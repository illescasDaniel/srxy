from __future__ import annotations

import sys
from pathlib import Path

import pytest
from tests.helpers import Product


def pytest_addoption(parser: pytest.Parser):
	parser.addoption(
		"--integration-test-cpu",
		action="store_true",
		default=False,
		help="Also run forced-CPU transcribe device matrix when CUDA is available",
	)


@pytest.fixture(autouse=True)
def isolate_gui_and_language(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
	"""Keep pytest from opening the desktop GUI; pin English for catalog assertions."""
	monkeypatch.setattr("srxy.application.launch.gui_importable", lambda: False)
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "srxy-settings.json"))
	monkeypatch.setenv("SRXY_LANGUAGE", "en")
	from srxy.i18n import set_language

	set_language("en")


def pytest_generate_tests(metafunc: pytest.Metafunc):
	if "device" not in metafunc.fixturenames:
		return
	if metafunc.definition.get_closest_marker("transcribe_device_matrix") is None:
		return
	from tests.helpers import transcribe_device_matrix_devices

	metafunc.parametrize("device", transcribe_device_matrix_devices(metafunc.config))


@pytest.fixture
def food_items() -> list[dict[str, str]]:
	return [
		{"name": "salt"},
		{"name": "salty"},
		{"name": "salad"},
	]


@pytest.fixture
def products() -> list[Product]:
	return [
		Product("spatial analyzer", "tool for spatial data", "software", "active", "spatializer"),
		Product("special offer", "limited time deal", "promo", "active"),
		Product("salad bowl", "fresh greens", "food", "active"),
		Product("inactive tool", "old spatial app", "software", "inactive", "spatial"),
	]


# Platform-specific tag tests run only on macOS/Windows; deselect elsewhere (not skip).
# Transcribe / model-load / OCR orientation probes need more than the default 60s.
_HEAVY_TIMEOUT_MARKERS = frozenset({"transcribe", "semantic", "integration", "ocr"})
_HEAVY_TIMEOUT_SECONDS = 300


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]):
	deselected: list[pytest.Item] = []
	remaining: list[pytest.Item] = []
	for item in items:
		if "macos_finder" in item.keywords and sys.platform != "darwin":
			deselected.append(item)
		elif "windows_tags" in item.keywords and sys.platform != "win32":
			deselected.append(item)
		else:
			remaining.append(item)
	if deselected:
		config.hook.pytest_deselected(items=deselected)
		items[:] = remaining

	timeout_mark = pytest.mark.timeout(_HEAVY_TIMEOUT_SECONDS)
	for item in items:
		if _HEAVY_TIMEOUT_MARKERS.intersection(item.keywords):
			item.add_marker(timeout_mark)
