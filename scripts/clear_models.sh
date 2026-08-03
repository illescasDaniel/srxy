#!/usr/bin/env bash
# Remove cached srxy model weights (not cache.db). See docs/power-ups.md.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=quality/internal/lib.sh
source "${script_dir}/quality/internal/lib.sh"

lib_require_venv
target="${1:-all}"
lib_uv_run python -m srxy.adapters.outbound.models.model_store clear "$target"
