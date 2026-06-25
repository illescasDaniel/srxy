#!/usr/bin/env bash

set -euo pipefail

internal_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${internal_dir}/lib.sh"

lib_require_venv
lib_activate_venv
PIPAPI_PYTHON_LOCATION="${LIB_REPO_ROOT}/.venv/bin/python" pip-audit --skip-editable
