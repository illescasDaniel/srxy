#!/usr/bin/env bash
# Copy .venv from the primary srxy checkout into the current worktree.
#
# Mirrors .venv from the primary checkout (the git worktree list entry that is
# NOT under $HOME/.cursor/worktrees/) into the current worktree using rsync,
# then runs uv sync to re-stamp activation-script paths for the new location.
# No packages are re-downloaded.
#
# Intended to be run from any linked worktree root. Devs can call it directly;
# agents invoke it via the copy-venv-to-worktree-srxy skill.
#
# Usage:
#   ./scripts/copy-venv.sh           # from worktree (or via skill path)
#   ./scripts/copy-venv.sh --force   # overwrite existing .venv

set -euo pipefail

FORCE=false
for arg in "$@"; do
	case "${arg}" in
	--force | -f)
		FORCE=true
		;;
	-h | --help)
		cat <<'EOF'
Usage: copy-venv.sh [--force|-f]

Copy .venv from the primary srxy checkout into this worktree, then run
uv sync --extra semantic to re-stamp activation-script paths.
EOF
		exit 0
		;;
	*)
		echo "error: unknown argument: ${arg}" >&2
		echo "Usage: copy-venv.sh [--force|-f]" >&2
		exit 1
		;;
	esac
done

# ---------------------------------------------------------------------------
# 1. Resolve current worktree root
# ---------------------------------------------------------------------------
if ! dest_root="$(git rev-parse --show-toplevel 2>&1)"; then
	echo "error: Not inside a git repository. Run this script from within a srxy worktree." >&2
	exit 1
fi

# ---------------------------------------------------------------------------
# 2. Parse git worktree list to find the primary checkout
# ---------------------------------------------------------------------------
if ! worktree_list="$(git worktree list 2>&1)"; then
	echo "error: git worktree list failed: ${worktree_list}" >&2
	exit 1
fi

cursor_worktrees="${HOME}/.cursor/worktrees"
primary_root=""
while IFS= read -r line; do
	[[ -z "${line}" ]] && continue
	candidate="${line%%[[:space:]]*}"
	[[ -z "${candidate}" ]] && continue
	# Primary checkout is never under $HOME/.cursor/worktrees/
	case "${candidate}/" in
	"${cursor_worktrees}"/*) continue ;;
	esac
	primary_root="${candidate}"
	break
done <<<"${worktree_list}"

if [[ -z "${primary_root}" ]]; then
	echo "error: Could not find the primary checkout in 'git worktree list'. Output was:" >&2
	echo "${worktree_list}" >&2
	exit 1
fi

# Strip trailing slashes for comparison
dest_cmp="${dest_root%/}"
primary_cmp="${primary_root%/}"
if [[ "${dest_cmp}" == "${primary_cmp}" ]]; then
	echo "Already in the primary checkout (${primary_root}). Nothing to copy."
	exit 0
fi

# ---------------------------------------------------------------------------
# 3. Validate source and destination
# ---------------------------------------------------------------------------
src_venv="${primary_root}/.venv"
dst_venv="${dest_root}/.venv"

if [[ ! -d "${src_venv}" ]]; then
	echo "error: Source .venv not found at: ${src_venv}" >&2
	echo "Run 'uv sync --extra semantic' in the primary checkout first, then re-run this script." >&2
	exit 1
fi

if [[ -e "${dst_venv}" && "${FORCE}" != true ]]; then
	echo "warning: Destination .venv already exists at: ${dst_venv}" >&2
	echo "Pass --force to overwrite it, or delete it manually and re-run." >&2
	exit 1
fi

if [[ -e "${dst_venv}" && "${FORCE}" == true ]]; then
	echo "copy-venv: removing existing destination .venv (--force)..."
	rm -rf "${dst_venv}"
fi

# ---------------------------------------------------------------------------
# 4. rsync mirror
# ---------------------------------------------------------------------------
if ! command -v rsync >/dev/null 2>&1; then
	echo "error: rsync is required but not found on PATH." >&2
	exit 1
fi

echo ""
echo "copy-venv: copying .venv"
echo "  from : ${src_venv}"
echo "  to   : ${dst_venv}"
echo ""

mkdir -p "${dst_venv}"
rsync -a --info=progress2 "${src_venv}/" "${dst_venv}/"

echo ""
echo "copy-venv: copy complete"

# ---------------------------------------------------------------------------
# 5. uv sync — re-stamp activation scripts for the new path
# ---------------------------------------------------------------------------
echo ""
echo "copy-venv: running 'uv sync --extra semantic' to fix activation-script paths..."
cd "${dest_root}"
uv sync --extra semantic

# ---------------------------------------------------------------------------
# 6. Verify
# ---------------------------------------------------------------------------
echo ""
echo "copy-venv: verifying torch..."
torch_check="$("${dst_venv}/bin/python" -c \
	"import torch; print(torch.__version__, 'cuda=' + str(torch.cuda.is_available()))" \
	2>&1 || true)"
echo "  torch: ${torch_check}"

echo ""
echo "copy-venv: done."
echo "  source : ${src_venv}"
echo "  dest   : ${dst_venv}"
