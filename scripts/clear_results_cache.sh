#!/usr/bin/env bash
# Remove srxy results cache (cache.db). See docs/power-ups.md.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=quality/internal/lib.sh
source "${script_dir}/quality/internal/lib.sh"

lib_require_venv
lib_uv_run python -c "from srxy.adapters.outbound.cache.cache import clear_results_cache; clear_results_cache()"
