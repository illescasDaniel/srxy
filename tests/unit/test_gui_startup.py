from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest


pytestmark = pytest.mark.unit


@pytest.mark.parametrize("app_launch", [False, True])
@pytest.mark.parametrize("raw", [None, ".", "relative folder/ñ #100%", "../sibling", "", "/missing/ñ #100%"])
def test_given_launch_context_when_selecting_initial_path_then_explicit_input_wins(
	tmp_path: Path, raw: str | None, app_launch: bool
):
	# given
	policy = importlib.import_module("srxy.application.gui_startup").initial_gui_search_path
	cwd, home = str(tmp_path / "caller"), str(tmp_path / "home")
	explicit = str(tmp_path / "missing" / "ñ #100%") if raw and raw.startswith("/") else raw

	# when
	selected = policy(explicit, app_launch=app_launch, cwd=cwd, home=home)

	# then
	if explicit is None:
		assert selected == (home if app_launch else cwd)
	elif explicit == "":
		assert selected == ""
	elif explicit == ".":
		assert selected == cwd
	else:
		expected = explicit if os.path.isabs(explicit) else os.path.join(cwd, explicit)
		assert selected == expected


@pytest.mark.parametrize("raw", [None, ".", "missing/ñ #100%", ""])
def test_given_unavailable_cwd_when_selecting_initial_path_then_falls_back_only_for_omission(raw: str | None):
	# given
	policy = importlib.import_module("srxy.application.gui_startup").initial_gui_search_path

	# when
	selected = policy(raw, app_launch=False, cwd=None, home="/home/example")

	# then
	assert selected == ("/home/example" if raw is None else raw)


@pytest.mark.parametrize("raw", [None, ".", "missing folder/ñ #100%", "link/../target", "~//target"])
def test_given_supplied_context_when_selecting_initial_path_then_no_environment_or_filesystem_io(
	monkeypatch: pytest.MonkeyPatch, tmp_path: Path, raw: str | None
):
	# given
	policy = importlib.import_module("srxy.application.gui_startup").initial_gui_search_path
	cwd, home = str(tmp_path / "unreadable"), str(tmp_path / "home")

	def forbidden(*args, **kwargs):
		pytest.fail("Startup policy must only use supplied path values")

	for name in ("cwd", "home", "stat", "resolve", "iterdir", "exists", "is_dir"):
		monkeypatch.setattr(Path, name, forbidden)
	for name in ("getcwd", "listdir", "scandir", "access", "walk"):
		monkeypatch.setattr(os, name, forbidden)

	# when
	selected = policy(raw, app_launch=False, cwd=cwd, home=home)

	# then
	if raw == "~//target":
		assert Path(selected) == Path(home) / "target"
	else:
		expected = cwd if raw in (None, ".") else os.path.join(cwd, raw)
		assert selected == expected


def test_given_named_user_path_when_selecting_then_leaves_existing_expansion_for_validation(tmp_path: Path):
	# given
	policy = importlib.import_module("srxy.application.gui_startup").initial_gui_search_path

	# when
	selected = policy("~anotheruser/documents", app_launch=False, cwd=str(tmp_path), home=str(tmp_path / "home"))

	# then
	assert selected == "~anotheruser/documents"


@pytest.mark.parametrize(
	"raw", ["~/ñ #100%", "~//ñ #100%", "~///ñ #100%"] + (["~\\\\\\\\ñ #100%"] if os.name == "nt" else [])
)
@pytest.mark.parametrize("home_suffix", ["", os.sep])
def test_given_home_relative_explicit_path_when_selecting_then_preserves_home_expansion(
	monkeypatch: pytest.MonkeyPatch, tmp_path: Path, raw: str, home_suffix: str
):
	# given
	from tests.helpers import set_fake_home

	policy = importlib.import_module("srxy.application.gui_startup").initial_gui_search_path
	home = tmp_path / "home"
	set_fake_home(monkeypatch, home)

	# when
	selected = policy(raw, app_launch=False, cwd=str(tmp_path / "caller"), home=str(home) + home_suffix)

	# then
	assert Path(selected) == home / "ñ #100%"


@pytest.mark.parametrize("app_launch", [False, True])
def test_given_symlink_parent_relative_path_when_selecting_then_preserves_requested_target(
	monkeypatch: pytest.MonkeyPatch, tmp_path: Path, app_launch: bool
):
	# given
	policy = importlib.import_module("srxy.application.gui_startup").initial_gui_search_path
	caller = tmp_path / "caller"
	caller.mkdir()
	external = tmp_path / "external"
	linked_directory = external / "child"
	linked_directory.mkdir(parents=True)
	requested_target = external / "target"
	requested_target.mkdir()
	(caller / "target").mkdir()
	try:
		(caller / "link").symlink_to(linked_directory, target_is_directory=True)
	except OSError:
		if os.name == "nt":
			pytest.skip("Directory symlink creation requires Windows symlink privileges")
		raise
	monkeypatch.chdir(caller)
	raw = os.path.join("link", "..", "target")
	original_target = Path(raw).resolve(strict=True)
	assert original_target == requested_target

	# when
	selected = policy(raw, app_launch=app_launch, cwd=str(caller), home=str(tmp_path / "home"))

	# then
	assert Path(selected).is_absolute()
	assert Path(selected).resolve(strict=True) == original_target


@pytest.mark.parametrize("app_launch", [False, True])
def test_given_missing_intermediate_directory_when_selecting_then_preserves_invalid_explicit_path(
	tmp_path: Path, app_launch: bool
):
	# given
	policy = importlib.import_module("srxy.application.gui_startup").initial_gui_search_path
	caller = tmp_path / "caller"
	caller.mkdir()
	(caller / "target").mkdir()
	raw = os.path.join("missing", "..", "target")

	# when
	selected = policy(raw, app_launch=app_launch, cwd=str(caller), home=str(tmp_path / "home"))

	# then
	assert selected == os.path.join(str(caller), raw)
	assert not Path(selected).exists()
