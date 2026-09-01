"""Contract tests for the Windows offline Inno Setup script (no ISCC run)."""

from __future__ import annotations

from pathlib import Path

import pytest

from srxy.adapters.inbound.installer.privacy import PRIVACY_NOTICE_VERSION


pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[2]
_ISS = _REPO / "packaging" / "windows" / "srxy-offline.iss"


@pytest.fixture(scope="module")
def iss_text() -> str:
	assert _ISS.is_file(), f"missing {_ISS}"
	return _ISS.read_text(encoding="utf-8")


def test_given_offline_iss_when_reading_then_declares_english_and_spanish(iss_text: str):
	assert 'Name: "english"' in iss_text
	assert 'Name: "spanish"' in iss_text
	assert "compiler:Default.isl" in iss_text
	assert r"compiler:Languages\Spanish.isl" in iss_text


def test_given_offline_iss_when_reading_then_engine_language_maps_spanish_to_es(iss_text: str):
	assert "function EngineLanguageCode: String;" in iss_text
	assert "CompareText(ActiveLanguage, 'spanish') = 0" in iss_text
	assert "Result := 'es'" in iss_text
	assert "Result := 'en'" in iss_text


def test_given_offline_iss_when_reading_then_build_engine_args_pass_language(iss_text: str):
	assert "function BuildEngineArgs(const Action: String): String;" in iss_text
	assert "' --language ' + EngineLanguageCode" in iss_text
	assert "' --privacy-ack ' + PrivacyAckVersionValue" in iss_text
	assert "if Action <> '--uninstall' then" in iss_text
	assert "Args := Args + ' --tesseract'" in iss_text
	assert "Args := Args + ' --ffmpeg'" in iss_text
	assert "Args := Args + ' --semantic'" in iss_text
	assert "Args := Args + ' --prefetch-models'" in iss_text
	assert "Args := Args + ' --add-path'" in iss_text
	assert "Args := Args + ' --no-add-path'" in iss_text


def test_given_offline_iss_when_reading_then_language_applies_to_uninstall_too(iss_text: str):
	# --language is outside the uninstall-only skip block (before privacy/components).
	build_start = iss_text.index("function BuildEngineArgs(const Action: String): String;")
	uninstall_guard = iss_text.index("if Action <> '--uninstall' then", build_start)
	language_arg = iss_text.index("' --language ' + EngineLanguageCode", build_start)
	assert language_arg < uninstall_guard


def test_given_offline_iss_when_reading_then_privacy_file_follows_active_language(iss_text: str):
	assert "function PrivacyFileForLanguage: String;" in iss_text
	assert "ActiveLanguage = 'spanish'" in iss_text
	assert "Result := 'privacy-es.txt'" in iss_text
	assert "Result := 'privacy-en.txt'" in iss_text


def test_given_offline_iss_when_reading_then_privacy_ack_define_matches_engine(
	iss_text: str,
):
	assert "#ifndef PrivacyAckVersion" in iss_text
	assert f'#define PrivacyAckVersion "{PRIVACY_NOTICE_VERSION}"' in iss_text


def test_given_offline_iss_when_reading_then_installing_page_retargets_uninstall(iss_text: str):
	"""Wizard uninstall must not leave Inno's default 'Installing' captions visible."""
	assert "CurPageID = wpInstalling" in iss_text
	assert "CustomMessage('WizardUninstalling')" in iss_text
	assert "CustomMessage('WizardUninstallingLabel')" in iss_text
	assert "CustomMessage('WizardReinstalling')" in iss_text
	assert "english.WizardUninstalling=Uninstalling" in iss_text
	assert "english.WizardUninstallingLabel=Please wait while Setup removes Srxy from your computer." in iss_text
	assert "spanish.WizardUninstalling=Desinstalando" in iss_text


def test_given_offline_iss_when_reading_then_engine_utf8_env_vars_set(iss_text: str):
	"""RunEngine must set PYTHONUTF8 + PYTHONIOENCODING so the log is valid Unicode."""
	assert "SetEnvironmentVariable('PYTHONUTF8', '1')" in iss_text
	assert "SetEnvironmentVariable('PYTHONIOENCODING', 'utf-8')" in iss_text


def test_given_offline_iss_when_reading_then_silent_skips_recommended_type_override(iss_text: str):
	"""Silent /COMPONENTS=core must not be overwritten by ApplyRecommendedSetupType."""
	assert "procedure CurPageChanged(CurPageID: Integer);" in iss_text
	assert "and (not WizardSilent) then" in iss_text
	cur = iss_text.index("procedure CurPageChanged(CurPageID: Integer);")
	apply = iss_text.index("ApplyRecommendedSetupType;", cur)
	silent_guard = iss_text.index("and (not WizardSilent) then", cur)
	assert silent_guard < apply


def test_given_offline_iss_when_reading_then_components_have_extra_disk_space(iss_text: str):
	assert "ExtraDiskSpaceRequired: 734003200" in iss_text
	assert 'Name: "tesseract"' in iss_text and "ExtraDiskSpaceRequired: 89128960" in iss_text
	assert "RefreshDiskSpaceLabel" in iss_text
	assert "ComputeRequiredInstallBytes" in iss_text


def test_given_offline_iss_when_reading_then_progress_uses_step_prefix_format(iss_text: str):
	assert "Primary := IntToStr(EnginePhaseIndex) + '/' + IntToStr(EnginePhaseTotal) + ' - ' + Primary" in iss_text


def test_given_offline_iss_when_reading_then_uninstall_cleanup_flags_exist(iss_text: str):
	assert "--remove-cache" in iss_text
	assert "--remove-settings" in iss_text
	assert "--remove-models" in iss_text
	assert "--cancel-file" in iss_text
	assert "UninstallExtrasPage" in iss_text
	assert "procedure CancelButtonClick(CurPageID: Integer; var Cancel, Confirm: Boolean);" in iss_text
	assert "OnCancelButtonClick" not in iss_text
