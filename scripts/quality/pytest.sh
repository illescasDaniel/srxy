#!/usr/bin/env bash

set -euo pipefail

quality_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=internal/lib.sh
source "${quality_dir}/internal/lib.sh"

lib_require_venv
lib_pytest_args

if [[ ${#LIB_PYTEST_ARGS[@]} -eq 0 ]]; then
	echo "No pytest test directory found (expected tests/ or test/)" >&2
	exit 1
fi

lib_uv_run pytest "${LIB_PYTEST_ARGS[@]}" "${LIB_PYTEST_COV[@]}"
pytest_exit=$?

if [[ "${pytest_exit}" -ne 0 ]]; then
	exit "${pytest_exit}"
fi

lib_pytest_gui_integration_args
if [[ ${#LIB_PYTEST_GUI_INTEGRATION_ARGS[@]} -gt 0 ]]; then
	echo ""
	echo "Serial GUI integration pass (QT_QPA_PLATFORM=offscreen, -n 0)"
	QT_QPA_PLATFORM=offscreen lib_uv_run pytest "${LIB_PYTEST_GUI_INTEGRATION_ARGS[@]}"
	pytest_exit=$?
fi

exit "${pytest_exit}"
