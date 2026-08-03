#!/usr/bin/env bash
# Launch the GUI from a separate core-only venv (no [semantic] extras).
# Does not modify the project .venv. Recreate with: uv run task gui-bare -- --recreate
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${SRXY_BARE_VENV:-$ROOT/.venv-bare}"
RECREATE=0
FORWARD=()

usage() {
	cat <<'EOF'
Launch srxy GUI from a gitignored core-only venv (.venv-bare).

No [semantic] extras → no PyTorch / sentence-transformers / Whisper, so Search
options shows unavailable warnings for smarter-search features.

Usage: scripts/gui-bare.sh [--recreate] [--] [srxy args...]

Options:
  --recreate   Delete and recreate .venv-bare, then reinstall core srxy
  -h, --help   Show this help

Environment:
  SRXY_BARE_VENV   Override venv path (default: <repo>/.venv-bare)
EOF
}

while [[ $# -gt 0 ]]; do
	case "$1" in
	--recreate)
		RECREATE=1
		shift
		;;
	-h | --help)
		usage
		exit 0
		;;
	--)
		shift
		FORWARD+=("$@")
		break
		;;
	*)
		FORWARD+=("$1")
		shift
		;;
	esac
done

cd "$ROOT"

if [[ "$RECREATE" -eq 1 && -d "$VENV" ]]; then
	echo "Removing $VENV …"
	rm -rf "$VENV"
fi

if [[ ! -x "$VENV/bin/python" ]]; then
	echo "Creating core-only venv at $VENV …"
	uv venv --python 3.12 "$VENV"
	uv pip install --python "$VENV/bin/python" -e "$ROOT"
fi

export SRXY_SKIP_UPDATE_CHECK="${SRXY_SKIP_UPDATE_CHECK:-1}"
# GUI is selected automatically when a display is available (same as `task gui`).
exec "$VENV/bin/srxy" "${FORWARD[@]}"
