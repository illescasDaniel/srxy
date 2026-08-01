#!/usr/bin/env bash

set -euo pipefail

internal_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${internal_dir}/lib.sh"

lib_require_venv
python_bin="$(lib_uv_run python -c 'import sys; print(sys.executable)')"
PIPAPI_PYTHON_LOCATION="${python_bin}" lib_uv_run pip-audit --skip-editable
