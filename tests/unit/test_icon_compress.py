from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image
from scripts.icon_compress import compress_png


pytestmark = pytest.mark.unit


def test_given_png_when_compress_png_then_invokes_pngquant(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	path = tmp_path / "icon.png"
	Image.new("RGBA", (8, 8), (255, 0, 0, 255)).save(path)
	run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
	monkeypatch.setattr("scripts.icon_compress.shutil.which", lambda _name: "/fake/pngquant")
	monkeypatch.setattr("scripts.icon_compress.subprocess.run", run)

	# when
	compress_png(path, quality=40)

	# then
	run.assert_called_once()
	args = run.call_args.args[0]
	assert args[0] == "/fake/pngquant"
	assert args[1] == "--quality=40-40"
	assert str(path) in args


def test_given_missing_pngquant_when_compress_png_then_exits_with_message(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setattr("scripts.icon_compress.shutil.which", lambda _name: None)

	# when / then
	with pytest.raises(SystemExit, match="pngquant not found"):
		compress_png(Path("icon.png"))
