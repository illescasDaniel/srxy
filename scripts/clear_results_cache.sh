#!/usr/bin/env bash
# Remove srxy results cache (cache.db). See docs/power-ups.md.
set -euo pipefail

exec python -m srxy.cache clear
