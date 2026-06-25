#!/usr/bin/env bash

set -euo pipefail

quality_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=internal/lib.sh
source "${quality_dir}/internal/lib.sh"

lib_require_venv
lib_activate_venv
lib_pytest_args

if [[ ${#LIB_PYTEST_ARGS[@]} -eq 0 ]]; then
	echo "No pytest test directory found (expected tests/ or test/)" >&2
	exit 1
fi

pytest "${LIB_PYTEST_ARGS[@]}" "${LIB_PYTEST_COV[@]}"
