#!/usr/bin/env bash
# Platform-aware uv sync. See scripts/dev/sync.py.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
sync_py="${script_dir}/sync.py"

if command -v uv >/dev/null 2>&1; then
	exec uv run --no-project python "${sync_py}" "$@"
fi
if command -v python3 >/dev/null 2>&1; then
	exec python3 "${sync_py}" "$@"
fi
if command -v python >/dev/null 2>&1; then
	exec python "${sync_py}" "$@"
fi
echo "error: need uv or python3 to run ${sync_py}" >&2
exit 1
