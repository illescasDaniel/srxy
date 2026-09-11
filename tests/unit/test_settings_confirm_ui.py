from __future__ import annotations

import pytest

from srxy.application.settings_maintenance import settings_confirm_ui
from srxy.i18n import set_language, tr


pytestmark = pytest.mark.unit


def test_given_reset_preferences_action_when_confirm_ui_then_title_and_reset_button():
	set_language("en")
	ui = settings_confirm_ui("reset_preferences")
	assert ui["title"] == tr("settings.confirm.title.reset_preferences")
	assert ui["acceptLabel"] == tr("settings.confirm.button.reset")
	assert "language, search options, and filters" in ui["message"]


def test_given_clear_cache_action_when_confirm_ui_then_title_and_reset_button():
	set_language("en")
	ui = settings_confirm_ui("clear_cache")
	assert ui["title"] == tr("settings.confirm.title.clear_cache")
	assert ui["acceptLabel"] == tr("settings.confirm.button.reset")
	assert "encrypted on disk" in ui["message"]


def test_given_clear_model_action_when_confirm_ui_then_delete_button():
	set_language("en")
	ui = settings_confirm_ui("clear_model:semantic_text")
	assert ui["acceptLabel"] == tr("settings.confirm.button.delete")
	assert "?" in ui["title"]
