#!/usr/bin/env bash
# Remove srxy results cache (cache.db). See docs/power-ups.md.
set -euo pipefail

exec python -c "from srxy.cache import clear_results_cache; clear_results_cache()"
