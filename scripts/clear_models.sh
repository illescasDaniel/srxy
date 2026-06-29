#!/usr/bin/env bash
# Remove cached srxy model weights (not cache.db). See docs/power-ups.md.
set -euo pipefail

target="${1:-all}"
exec python -m srxy.model_store clear "$target"
