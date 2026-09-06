from __future__ import annotations

from unittest.mock import patch

import pytest

from srxy.adapters.inbound.installer import probe_catalog
from srxy.adapters.inbound.installer.resolve import ResolvedArtifact


pytestmark = pytest.mark.unit


def _artifact(url: str) -> ResolvedArtifact:
	return ResolvedArtifact(name="x", version="1", url=url, sha256="", kind="file")


def test_given_all_resolvers_succeed_when_probing_then_returns_all_targets_and_no_unresolvable():
	# given
	with (
		patch.object(probe_catalog, "resolve_ffmpeg_btbn", return_value=_artifact("https://a")),
		patch.object(probe_catalog, "resolve_ffmpeg_martin_riedl", return_value=_artifact("https://b")),
		patch.object(probe_catalog, "resolve_tesseract_linux", return_value=_artifact("https://c")),
		patch.object(probe_catalog, "resolve_tesseract_windows", return_value=_artifact("https://d")),
		patch.object(
			probe_catalog,
			"resolve_tesseract_brew_bottles",
			return_value=(_artifact("https://e"),),
		),
	):
		# when
		targets, unresolvable = probe_catalog._probe_resolvers()  # pyright: ignore[reportPrivateUsage]

	# then
	assert unresolvable == []
	assert len(targets) == 8  # 4 ffmpeg/tesseract singles + 2 darwin brew-bottle machines... see below
	labels = {label for label, _url, _headers in targets}
	assert "resolve:tesseract/darwin-x86_64" in labels
	assert "resolve:tesseract/darwin-arm64" in labels


def test_given_one_resolver_raises_when_probing_then_skips_only_that_target(monkeypatch: pytest.MonkeyPatch):
	# given — upstream catalog drift (e.g. Homebrew dropping a bottle tag) should not
	# hide probe results for the other, unrelated resolvers.
	def fake_brew_bottles(*, machine: str):
		if machine == "x86_64":
			raise RuntimeError("no matching bottle tag for jpeg-turbo (tried sonoma, ventura, monterey)")
		return (_artifact("https://arm64-bottle"),)

	with (
		patch.object(probe_catalog, "resolve_ffmpeg_btbn", return_value=_artifact("https://a")),
		patch.object(probe_catalog, "resolve_ffmpeg_martin_riedl", return_value=_artifact("https://b")),
		patch.object(probe_catalog, "resolve_tesseract_linux", return_value=_artifact("https://c")),
		patch.object(probe_catalog, "resolve_tesseract_windows", return_value=_artifact("https://d")),
		patch.object(probe_catalog, "resolve_tesseract_brew_bottles", side_effect=fake_brew_bottles),
	):
		# when
		targets, unresolvable = probe_catalog._probe_resolvers()  # pyright: ignore[reportPrivateUsage]

	# then
	assert unresolvable == ["tesseract/darwin-x86_64"]
	labels = {label for label, _url, _headers in targets}
	assert "resolve:tesseract/darwin-x86_64" not in labels
	assert "resolve:tesseract/darwin-arm64" in labels
	assert "resolve:ffmpeg/linux" in labels


def test_given_unresolvable_resolver_when_running_main_then_exits_zero_with_note(
	monkeypatch: pytest.MonkeyPatch,
):
	# given — a resolver-only failure (no broken catalog pin) must not fail CI
	with (
		patch.object(probe_catalog, "_probe_catalog_maps", return_value=[]),
		patch.object(
			probe_catalog,
			"_probe_resolvers",
			return_value=([], ["tesseract/darwin-x86_64"]),
		),
	):
		# when
		exit_code = probe_catalog.main([])

	# then
	assert exit_code == 0


def test_given_broken_catalog_pin_when_running_main_then_exits_nonzero(monkeypatch: pytest.MonkeyPatch):
	# given — a genuinely broken sha256-pinned catalog URL must still fail CI
	with (
		patch.object(probe_catalog, "_probe_catalog_maps", return_value=[("catalog:linux/uv", "https://dead", None)]),
		patch.object(probe_catalog, "_probe_resolvers", return_value=([], [])),
		patch.object(probe_catalog, "probe_url", side_effect=RuntimeError("404")),
	):
		# when
		exit_code = probe_catalog.main([])

	# then
	assert exit_code == 1
