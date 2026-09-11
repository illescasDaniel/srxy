"""Unit tests for copy-venv rewrite_venv_paths helper."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
REWRITE_SCRIPT = REPO_ROOT / ".cursor" / "skills" / "copy-venv-to-worktree-srxy" / "scripts" / "rewrite_venv_paths.py"


def _load_rewrite_module():
	spec = importlib.util.spec_from_file_location("rewrite_venv_paths", REWRITE_SCRIPT)
	assert spec is not None and spec.loader is not None
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def _make_fake_venv(old_root: Path, new_root: Path) -> Path:
	"""Create a minimal copied-venv layout under new_root/.venv with old paths."""
	venv = new_root / ".venv"
	bin_dir = venv / "bin"
	site = venv / "lib" / "python3.12" / "site-packages"
	dist = site / "srxy-1.7.0.dist-info"
	bin_dir.mkdir(parents=True)
	site.mkdir(parents=True)
	dist.mkdir(parents=True)

	old_python = f"{old_root.as_posix()}/.venv/bin/python"
	(bin_dir / "pytest").write_text(
		f"#!{old_python}\nimport pytest\n",
		encoding="utf-8",
	)
	(bin_dir / "activate").write_text(
		f"VIRTUAL_ENV='{old_root.as_posix()}/.venv'\nexport VIRTUAL_ENV\n",
		encoding="utf-8",
	)
	(site / "srxy.pth").write_text(f"{old_root.as_posix()}/src\n", encoding="utf-8")
	(dist / "direct_url.json").write_text(
		f'{{"url":"file://{old_root.as_posix()}","dir_info":{{"editable":true}}}}\n',
		encoding="utf-8",
	)
	(venv / "pyvenv.cfg").write_text(
		"home = /opt/uv/python/bin\ninclude-system-site-packages = false\nprompt = srxy\n",
		encoding="utf-8",
	)
	# Native-looking binary must be left alone even if it somehow contained text
	# (NUL in first KiB → skipped as non-text).
	(bin_dir / "ruff").write_bytes(b"\x7fELF" + b"\0" * 32 + old_root.as_posix().encode())
	return venv


def test_given_copied_venv_with_primary_paths_when_rewriting_then_shebang_pth_and_direct_url_use_worktree(
	tmp_path: Path,
):
	# given
	rewrite = _load_rewrite_module()
	old_root = tmp_path / "primary" / "srxy"
	new_root = tmp_path / "worktree" / "meko"
	old_root.mkdir(parents=True)
	new_root.mkdir(parents=True)
	venv = _make_fake_venv(old_root, new_root)
	old_posix = old_root.resolve().as_posix()
	new_posix = new_root.resolve().as_posix()

	# when
	counts = rewrite.rewrite_venv_paths(old_root, new_root)

	# then
	assert counts["text"] >= 3
	pytest_shebang = (venv / "bin" / "pytest").read_text(encoding="utf-8").splitlines()[0]
	assert pytest_shebang.startswith(f"#!{new_posix}/.venv/bin/python")
	assert old_posix not in pytest_shebang
	assert (venv / "lib" / "python3.12" / "site-packages" / "srxy.pth").read_text(
		encoding="utf-8"
	).strip() == f"{new_posix}/src"
	direct_url = (venv / "lib" / "python3.12" / "site-packages" / "srxy-1.7.0.dist-info" / "direct_url.json").read_text(
		encoding="utf-8"
	)
	assert f"file://{new_posix}" in direct_url
	assert old_posix not in direct_url
	activate = (venv / "bin" / "activate").read_text(encoding="utf-8")
	assert f"{new_posix}/.venv" in activate
	assert old_posix not in activate
	# ELF-like binary unchanged (still contains old path bytes).
	assert old_posix.encode() in (venv / "bin" / "ruff").read_bytes()


def test_given_identical_roots_when_rewriting_then_exits_nonzero(tmp_path: Path):
	# given
	rewrite = _load_rewrite_module()
	root = tmp_path / "same"
	root.mkdir()
	(root / ".venv" / "bin").mkdir(parents=True)
	(root / ".venv" / "bin" / "pytest").write_text(
		f"#!{root.as_posix()}/.venv/bin/python\n",
		encoding="utf-8",
	)

	# when / then
	with pytest.raises(SystemExit) as excinfo:
		rewrite.rewrite_venv_paths(root, root)
	assert excinfo.value.code == 1
