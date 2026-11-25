#!/usr/bin/env python3
"""Export a project's agent sessions (Claude Code, Codex, opencode) to condensed, redacted Markdown.

Keeps only what the user and the assistant said to each other: no tool calls, tool output, reasoning or injected
instructions. One file per session, named <first date>-<session id prefix>.md. A file is rewritten only when its
session has grown, so the script is safe to run at the end of every session.

usage: export_sessions.py [--project DIR] [--out DIR] [--since YYYY-MM-DD] [--max-chars N] [--dry-run]
       export_sessions.py --claude-dir DIR ...   (moved project, or worktrees outside it; repeatable)
Prints one line per new or updated file; add those to sessions/INDEX.md.
In a git repository the sessions of all its worktrees are collected, and from a linked worktree the default --out is
the main checkout's memory/sessions (linked from the worktree when possible). The archive is kept out of git by a
`/sessions` line in memory/.gitignore, which the script adds when it is missing.
Standard library only; Python 3.9+.
"""
import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from functools import partial
from pathlib import Path

HOME = Path.home()
CLAUDE_ROOT = Path(os.environ.get("CLAUDE_CONFIG_DIR", HOME / ".claude")) / "projects"
CODEX_ROOT = Path(os.environ.get("CODEX_HOME", HOME / ".codex")) / "sessions"
OPENCODE_DB = Path(os.environ.get("XDG_DATA_HOME") or HOME / ".local" / "share") / "opencode" / "opencode.db"

# Injected context rather than conversation.
SKIP_PREFIXES = (
    "<command-", "<local-command", "<system-reminder", "<task-notification", "<environment_context",
    "<user_instructions", "<permissions instructions", "<user_shell_command", "# AGENTS.md instructions",
    "Caveat:", "This session is being continued", "[Request interrupted",
)

# Credential-shaped strings. Conservative: a false positive costs a few characters of context.
R = "[REDACTED]"
SECRET_PATTERNS = [  # (pattern, replacement)
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", R),
    (r"\b(?:sk|pk|rk)-(?:ant-|proj-|live-|test-)?[A-Za-z0-9_\-]{16,}", R),
    (r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}|\bgithub_pat_[A-Za-z0-9_]{20,}", R),
    (r"\bglpat-[A-Za-z0-9_\-]{20,}|\bhf_[A-Za-z0-9]{20,}|\bnpm_[A-Za-z0-9]{30,}|\bpypi-[A-Za-z0-9_\-]{30,}", R),
    (r"\bxox[abposr]-[A-Za-z0-9\-]{10,}|\bAKIA[0-9A-Z]{16}\b|\bAIza[0-9A-Za-z_\-]{30,}", R),
    (r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}", R),                 # JWT
    (r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=\-]{20,}", r"\1 " + R),
    (r"(?i)\b([a-z0-9_]*(?:password|passwd|secret|token|api[_-]?key|access[_-]?key)[a-z0-9_]*\s*[:=]\s*[\"']?)"
     r"(?!\[REDACTED)[^\s\"'`,;]{8,}", r"\1" + R),
    (r"(?i)\b([a-z][a-z0-9+.\-]*://[^\s:/@]+:)[^\s@/]{4,}@", r"\1" + R + "@"),             # user:pass@host
]
SECRET_PATTERNS = [(re.compile(p, re.S), r) for p, r in SECRET_PATTERNS]


def redact(text):
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def clip(text, limit):
    if limit and len(text) > limit:
        return text[:limit] + f"\n[... {len(text) - limit} more characters not exported]"
    return text


def claude_text(content):
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text")


def read_claude(path):
    """Yield (role, timestamp, text) from a Claude Code transcript; drops subagent, meta and tool turns."""
    with path.open(encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            try:
                event = json.loads(raw)
            except ValueError:
                continue
            if event.get("type") not in ("user", "assistant") or event.get("isSidechain") or event.get("isMeta"):
                continue
            text = claude_text((event.get("message") or {}).get("content")).strip()
            if text:
                yield event["type"], event.get("timestamp", ""), text


def codex_meta(path):
    with path.open(encoding="utf-8", errors="replace") as fh:
        for _, raw in zip(range(5), fh):
            try:
                event = json.loads(raw)
            except ValueError:
                continue
            if event.get("type") == "session_meta":
                return event.get("payload") or {}
    return {}


def read_codex(path):
    """Yield (role, timestamp, text) from a Codex rollout file; drops developer, reasoning and tool items."""
    with path.open(encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            try:
                event = json.loads(raw)
            except ValueError:
                continue
            item = event.get("payload") or {}
            if event.get("type") != "response_item" or item.get("type") != "message":
                continue
            role = item.get("role")
            if role not in ("user", "assistant"):
                continue
            text = "\n".join(b.get("text", "") for b in item.get("content") or []
                             if isinstance(b, dict) and b.get("type") in ("input_text", "output_text")).strip()
            if text:
                yield role, event.get("timestamp", ""), text


def opencode_db(note=True):
    """Open opencode's database read-only, or return None (missing, locked or unreadable) with one short note."""
    if not OPENCODE_DB.is_file():
        return None
    try:
        return sqlite3.connect(OPENCODE_DB.resolve().as_uri() + "?mode=ro", uri=True, timeout=1)
    except sqlite3.Error as err:
        if note:
            print(f"opencode: cannot open its database ({err}); skipped", file=sys.stderr)
        return None


def opencode_sessions(roots):
    """Return ids of opencode's own (not subagent) sessions whose working directory is inside the project or a worktree."""
    db = opencode_db()
    if not db:
        return []
    try:
        with db:
            rows = db.execute("SELECT id, directory FROM session_v2 WHERE parent_id IS NULL ORDER BY time_created").fetchall()
    except sqlite3.Error as err:
        print(f"opencode: cannot read its sessions ({err}); skipped", file=sys.stderr)
        return []
    finally:
        db.close()
    return [sid for sid, directory in rows if any(inside(directory, root) for root in roots)]


def read_opencode(sid, path):
    """Yield (role, timestamp, text) from an opencode session; drops reasoning, tool items and compaction summaries."""
    db = opencode_db(note=False)
    if not db:
        return
    try:
        with db:
            rows = db.execute("SELECT type, time_created, data FROM session_message WHERE session_id = ? "
                              "AND type IN ('user', 'assistant') ORDER BY seq", (sid,)).fetchall()
    except sqlite3.Error:
        return
    finally:
        db.close()
    for role, millis, raw in rows:
        try:
            data = json.loads(raw)
            if role == "user":
                text = data.get("text")
            else:
                text = "\n".join(b.get("text", "") for b in data.get("content") or []
                                 if isinstance(b, dict) and b.get("type") == "text")
            stamp = datetime.fromtimestamp(millis / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, AttributeError, TypeError, OverflowError, OSError):
            continue
        if isinstance(text, str) and text.strip():
            yield role, stamp, text.strip()


def claude_cwd(path):
    with path.open(encoding="utf-8", errors="replace") as fh:
        for _, raw in zip(range(50), fh):
            try:
                cwd = json.loads(raw).get("cwd")
            except (ValueError, AttributeError):
                continue
            if cwd:
                return cwd
    return None


def inside(cwd, project):
    return bool(cwd) and (Path(cwd) == project or project in Path(cwd).parents)


def git_out(project, *args):
    """Stdout of `git -C project args`, or None when git is missing, fails or is not a repository."""
    try:
        done = subprocess.run(["git", "-C", str(project), *args], capture_output=True, text=True, check=False, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def git_layout(project):
    """Return (in_repo, main checkout when project is a linked worktree else None, every worktree path of the repo)."""
    git_dir, common, top = (git_out(project, "rev-parse", *a) for a in (("--git-dir",), ("--git-common-dir",), ("--show-toplevel",)))
    if not (git_dir and common and top and Path(top).resolve() == project):
        return False, None, [project]
    git_dir, common = (Path(project, d).resolve() for d in (git_dir, common))  # relative answers are relative to project
    main = common.parent if git_dir != common and common.name == ".git" else None
    roots = [project] + [Path(line[9:]).resolve() for line in (git_out(project, "worktree", "list", "--porcelain") or "").splitlines()
                         if line.startswith("worktree ")]
    return True, main, list(dict.fromkeys(roots))


def link_archive(local, target):
    """Best effort: make a worktree's memory/sessions a symlink to the main checkout's archive."""
    try:
        if local.is_symlink() or (local.exists() and (not local.is_dir() or any(local.iterdir()))):
            return
        target.mkdir(parents=True, exist_ok=True)
        if local.exists():
            local.rmdir()
        local.parent.mkdir(parents=True, exist_ok=True)
        local.symlink_to(target, target_is_directory=True)
    except OSError as err:
        print(f"could not link {local} to {target} ({err}); sessions are still written there", file=sys.stderr)


def ensure_ignored(out):
    """Keep the archive out of git: a `/sessions` line in the memory folder's .gitignore (no slash at the end, so it
    also matches a symlink)."""
    gitignore = out.parent / ".gitignore"
    try:
        old = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
        if any(line.strip() in ("/sessions", "/sessions/", "sessions", "sessions/") for line in old.splitlines()):
            return
        gitignore.write_text(old + ("\n" if old and not old.endswith("\n") else "") + "/sessions\n", encoding="utf-8")
    except OSError as err:
        print(f"could not update {gitignore} ({err}); keep {out.name}/ out of git yourself", file=sys.stderr)


def find_sessions(project, claude_dirs, roots=None):
    roots = roots or [project]
    found = []
    if claude_dirs:
        found += [("claude", p, read_claude) for d in claude_dirs for p in sorted(Path(d).glob("*.jsonl"))]
    elif CLAUDE_ROOT.is_dir():
        # Claude Code keeps a project's sessions under its absolute path with every non-alphanumeric character as "-";
        # worktrees inside the project get sibling folders with a longer name. Confirm each by its recorded cwd.
        encoded = [re.sub(r"[^A-Za-z0-9]", "-", str(root)) for root in roots]
        for cdir in sorted(CLAUDE_ROOT.iterdir()):
            if any(cdir.name == enc or cdir.name.startswith(enc + "-") for enc in encoded):
                found += [("claude", p, read_claude) for p in sorted(cdir.glob("*.jsonl"))
                          if cdir.name in encoded or any(inside(claude_cwd(p), root) for root in roots)]
    if CODEX_ROOT.is_dir():
        for path in sorted(CODEX_ROOT.rglob("*.jsonl")):
            meta = codex_meta(path)
            # Codex stores each subagent and automatic review as its own rollout; only the user's own sessions count.
            if any(inside(meta.get("cwd"), root) for root in roots) and not (isinstance(meta.get("source"), dict) and "subagent" in meta["source"]):
                found.append(("codex", path, read_codex))
    found += [("opencode", OPENCODE_DB, partial(read_opencode, sid)) for sid in opencode_sessions(roots)]
    return found


def render(client, path, reader, max_chars):
    turns = []
    for role, stamp, text in reader(path):
        if text.startswith(SKIP_PREFIXES):
            continue
        turns.append((role, stamp, redact(clip(text, max_chars))))
    if not turns or not any(r == "user" for r, _, _ in turns):
        return None, None
    first, last = turns[0][1], turns[-1][1]
    # Claude Code ids are random UUIDs; Codex and opencode ids are time-ordered, so take their random tail instead.
    stem = reader.args[0] if client == "opencode" else path.stem  # an opencode session is a row, not a file
    sid = stem[:8] if client == "claude" else stem[-8:]
    name = f"{first[:10] or 'undated'}-{sid}.md"
    body = [f"# Session {stem} ({client})\n\n{first[:16].replace('T', ' ')} to {last[:16].replace('T', ' ')} UTC, "
            f"{len(turns)} messages. Tool calls and outputs are not exported.\n"]
    body += [f"### {role} {stamp[:16].replace('T', ' ')}\n{text}\n" for role, stamp, text in turns]
    return name, "\n".join(body)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project", default=".", help="project root whose sessions to export (default: .)")
    ap.add_argument("--out", help="output folder (default: memory/sessions, or the main checkout's when run in a "
                    "linked git worktree)")
    ap.add_argument("--claude-dir", action="append", help="Claude Code transcript folder to use instead of the "
                    "default lookup (repeatable; for moved projects or worktrees outside the project)")
    ap.add_argument("--since", help="only sessions whose first message is on or after this date (YYYY-MM-DD)")
    ap.add_argument("--max-chars", type=int, default=6000, help="cap per message, 0 for none (default: 6000)")
    ap.add_argument("--dry-run", action="store_true", help="list what would be written")
    args = ap.parse_args(argv)

    project = Path(args.project).resolve()
    in_repo, main_checkout, roots = git_layout(project)
    out = Path(args.out) if args.out else Path("memory/sessions")
    if not args.out and main_checkout:
        out = main_checkout / "memory" / "sessions"
        if not args.dry_run:
            link_archive(project / "memory" / "sessions", out)
    sessions = find_sessions(project, args.claude_dir, roots)
    if not sessions:
        print(f"no Claude Code, Codex or opencode sessions found for {project}", file=sys.stderr)
        return 1
    rendered = {}
    for client, path, reader in sessions:
        name, text = render(client, path, reader, args.max_chars)
        # A resumed or forked session can appear in two folders under one id: keep the longer copy.
        if name and not (args.since and name[:10] < args.since) and len(text) > len(rendered.get(name, ("", ""))[1]):
            rendered[name] = (client, text)
    counts = {"new": 0, "updated": 0, "unchanged": 0}
    for name, (client, text) in sorted(rendered.items()):
        target = out / name
        old = target.read_text(encoding="utf-8") if target.exists() else None
        state = "new" if old is None else "unchanged" if old == text else "updated"
        counts[state] += 1
        if state == "unchanged":
            continue
        if not args.dry_run:
            out.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            if in_repo and out.name == "sessions" and inside(out.resolve(), main_checkout or project):
                ensure_ignored(out.resolve())
        print(f"{state:8} {target}  ({client}, {len(text) // 1024} KB)")
    print(", ".join(f"{v} {k}" for k, v in counts.items()), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
