"""Unit tests for splash bridge metadata helpers."""

from __future__ import annotations

import os

import pytest
from PySide6.QtCore import QCoreApplication

from srxy.adapters.inbound.gui.splash import (
	SplashBridge,
	package_author_label,
	package_version_label,
)
from srxy.application.branding import AUTHOR


pytestmark = [pytest.mark.unit, pytest.mark.xdist_group("gui")]


@pytest.fixture(scope="module")
def qapp() -> QCoreApplication:
	os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
	app = QCoreApplication.instance()
	if app is None:
		from PySide6.QtGui import QGuiApplication

		app = QGuiApplication([])
	assert isinstance(app, QCoreApplication)
	return app


def test_given_package_metadata_when_reading_author_then_matches_branding_or_meta():
	assert package_author_label() == AUTHOR or "Illescas" in package_author_label()


def test_given_package_metadata_when_reading_version_then_nonzero():
	assert package_version_label()
	assert package_version_label() != ""


def test_given_splash_bridge_when_set_status_then_notifies(qapp: QCoreApplication):
	_ = qapp
	bridge = SplashBridge()
	assert bridge.appName == "srxy"
	assert bridge.author
	assert bridge.version
	status0 = str(bridge.property("status"))
	assert "Loading" in status0
	seen: list[str] = []
	bridge.statusChanged.connect(lambda: seen.append(str(bridge.property("status"))))
	bridge.set_status("Starting services…")
	assert str(bridge.property("status")) == "Starting services…"
	assert seen == ["Starting services…"]
