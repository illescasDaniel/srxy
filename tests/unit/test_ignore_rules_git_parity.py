from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from srxy.domain.ignore_rules import IgnoreMatcher, IgnoreSpec


pytestmark = [
	pytest.mark.unit,
	pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed"),
]

# (relative path, is_dir). Symlinks are deliberately excluded: srxy differs from git there.
_TREE: tuple[tuple[str, bool], ...] = (
	("start", False),
	("a", True),
	("a/start", False),
	("b", True),
	("b/start", True),
	("b/start/inner.txt", False),
	("logs", True),
	("logs/app.txt", False),
	("x", True),
	("x/logs", False),
	("debug.log", False),
	("keep.log", False),
	("a/keep.log", False),
	("a/debug.log", False),
	("Build", True),
	("Build/out.o", False),
	("build.txt", False),
	("docs", True),
	("docs/draft2.md", False),
	("docs/a", True),
	("docs/a/b", True),
	("docs/a/b/draft1.md", False),
	("docs/a/b/final.md", False),
	("other", True),
	("other/docs", True),
	("other/docs/draft3.md", False),
	("deep", False),
	("p", True),
	("p/q", True),
	("p/q/deep", False),
	("abc", True),
	("abc/x", False),
	("abc/y", True),
	("abc/y/z.txt", False),
	("ab.md", False),
	("a.md", False),
	("bx.txt", False),
	("dx.txt", False),
	("#hash", False),
	("!bang", False),
	("a*b", False),
	("aXb", False),
	("f.TXT", False),
)

_PATTERN_SETS: tuple[tuple[str, ...], ...] = (
	("start",),
	("/start",),
	("start/",),
	("logs/",),
	("*.log", "!keep.log"),
	("build/", "!build/out.o"),
	("Build/",),
	("build/",),
	("docs/**/draft*",),
	("**/deep",),
	("abc/**",),
	("a/**/z.txt",),
	("?.md",),
	("[a-c]x*",),
	("[!a-c]x*",),
	("\\#hash", "\\!bang"),
	("a\\*b",),
	("*.txt", "!f.txt"),
	("/a/", "!/a/keep.log"),
	("# comment", "", "*.log"),
	("!keep.log", "*.log"),
	("**/logs/", "x"),
)


@pytest.fixture(scope="module")
def repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
	root = tmp_path_factory.mktemp("parity_repo")
	for rel, is_dir in _TREE:
		target = root / rel
		if is_dir:
			target.mkdir(parents=True, exist_ok=True)
		else:
			target.parent.mkdir(parents=True, exist_ok=True)
			target.write_text("x")
	_git(root, "init", "-q")
	_git(root, "config", "core.ignorecase", "true")
	return root


def _git(root: Path, *args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
	env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
	return subprocess.run(["git", *args], cwd=root, input=stdin, capture_output=True, env=env, check=False)  # noqa: S603, S607


def _git_ignored(root: Path) -> set[str]:
	payload = b"\0".join(rel.encode() for rel, _ in _TREE) + b"\0"
	result = _git(root, "check-ignore", "--no-index", "-z", "--stdin", stdin=payload)
	assert result.returncode in (0, 1), result.stderr
	return {item.decode() for item in result.stdout.split(b"\0") if item}


def _srxy_ignored(patterns: tuple[str, ...]) -> set[str]:
	matcher = IgnoreMatcher.from_spec(IgnoreSpec(patterns=patterns))
	ignored: set[str] = set()
	for rel, is_dir in _TREE:
		parts = tuple(rel.split("/"))
		# Top-down like the walker: an ignored parent folder hides everything under it.
		if any(matcher.is_ignored(parts[:depth], True) for depth in range(1, len(parts))):
			ignored.add(rel)
		elif matcher.is_ignored(parts, is_dir):
			ignored.add(rel)
	return ignored


@pytest.mark.parametrize("patterns", _PATTERN_SETS, ids=lambda patterns: " | ".join(patterns))
def test_given_pattern_set_when_compared_with_git_check_ignore_then_same_paths_ignored(
	repo: Path, patterns: tuple[str, ...]
):
	# given
	(repo / ".gitignore").write_text("\n".join(patterns) + "\n")

	# when
	expected = _git_ignored(repo)
	actual = _srxy_ignored(patterns)

	# then
	assert actual == expected
