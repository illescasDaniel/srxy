from __future__ import annotations

from pathlib import Path

import pytest

from srxy.adapters.inbound.installer.path_setup import (
	PATH_BEGIN,
	PATH_END,
	ensure_path_block,
	remove_path_block,
	remove_srxy_path_from_shell,
)


pytestmark = pytest.mark.unit


def test_given_incomplete_path_block_when_removing_then_leaves_file_intact(tmp_path: Path):
	# given
	rc = tmp_path / ".zshrc"
	rc.write_text(
		"\n".join(
			[
				"# user config",
				PATH_BEGIN,
				'export PATH="/tmp/srxy/bin:$PATH"',
				"# missing end marker on purpose",
				"alias ll='ls -la'",
				"",
			]
		),
		encoding="utf-8",
	)
	original = rc.read_text(encoding="utf-8")

	# when
	result = remove_path_block(rc)

	# then
	assert result.changed is False
	assert result.incomplete_block is True
	assert rc.read_text(encoding="utf-8") == original


def test_given_complete_path_block_when_removing_then_strips_block_only(tmp_path: Path):
	# given
	rc = tmp_path / ".bashrc"
	rc.write_text(
		"\n".join(
			[
				"# before",
				PATH_BEGIN,
				'export PATH="/tmp/srxy/bin:$PATH"',
				PATH_END,
				"# after",
				"",
			]
		),
		encoding="utf-8",
	)

	# when
	result = remove_path_block(rc)

	# then
	assert result.changed is True
	assert result.incomplete_block is False
	text = rc.read_text(encoding="utf-8")
	assert PATH_BEGIN not in text
	assert PATH_END not in text
	assert "# before" in text
	assert "# after" in text


def test_given_recorded_rc_when_uninstalling_path_then_removes_that_file_only(tmp_path: Path):
	# given
	recorded = tmp_path / "custom-shell.rc"
	other = tmp_path / "other-shell.rc"
	for path in (recorded, other):
		path.write_text(
			"\n".join(
				[
					PATH_BEGIN,
					'export PATH="/tmp/srxy/bin:$PATH"',
					PATH_END,
					"",
				]
			),
			encoding="utf-8",
		)

	# when
	result = remove_srxy_path_from_shell(rc_path=recorded)

	# then
	assert result.changed is True
	assert PATH_BEGIN not in recorded.read_text(encoding="utf-8")
	assert PATH_BEGIN in other.read_text(encoding="utf-8")


def test_given_bin_dir_when_ensuring_path_block_then_writes_markers(tmp_path: Path):
	# given
	rc = tmp_path / ".zshrc"
	bin_dir = tmp_path / "Applications" / "srxy" / "bin"
	bin_dir.mkdir(parents=True)

	# when
	written = ensure_path_block(bin_dir, shell_name="zsh", rc_path=rc)

	# then
	assert written == rc
	text = rc.read_text(encoding="utf-8")
	assert PATH_BEGIN in text
	assert PATH_END in text
	assert str(bin_dir.resolve()) in text or str(bin_dir) in text


def test_given_windows_marker_when_removing_path_then_uses_user_path_helper(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	# given
	from srxy.adapters.inbound.installer import path_setup as path_setup_mod

	calls: list[Path | None] = []

	def fake_remove(bin_dir: Path | None = None):
		calls.append(bin_dir)
		return path_setup_mod.PathBlockRemovalResult(changed=True)

	monkeypatch.setattr(path_setup_mod, "_is_windows", lambda: True)
	monkeypatch.setattr(path_setup_mod, "remove_windows_user_path", fake_remove)

	# when
	result = remove_srxy_path_from_shell(
		rc_path=path_setup_mod.WINDOWS_USER_PATH_MARKER,
		bin_dir=tmp_path / "bin",
	)

	# then
	assert result.changed is True
	assert calls == [tmp_path / "bin"]


def test_given_windows_when_ensuring_path_without_rc_then_uses_user_path(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	# given
	from srxy.adapters.inbound.installer import path_setup as path_setup_mod

	bin_dir = tmp_path / "Programs" / "srxy" / "bin"
	bin_dir.mkdir(parents=True)
	seen: list[Path] = []

	def fake_ensure(path: Path) -> str:
		seen.append(path)
		return path_setup_mod.WINDOWS_USER_PATH_MARKER

	monkeypatch.setattr(path_setup_mod, "_is_windows", lambda: True)
	monkeypatch.setattr(path_setup_mod, "ensure_windows_user_path", fake_ensure)

	# when
	result = ensure_path_block(bin_dir)

	# then
	assert result == path_setup_mod.WINDOWS_USER_PATH_MARKER
	assert seen == [bin_dir]
