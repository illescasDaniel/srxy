#!/usr/bin/env bash

set -euo pipefail

quality_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=internal/lib.sh
source "${quality_dir}/internal/lib.sh"

CHECK_ONLY=false
GITHUB_OUTPUT=false
for arg in "$@"; do
	case "${arg}" in
	--check)
		CHECK_ONLY=true
		;;
	--github)
		GITHUB_OUTPUT=true
		;;
	esac
done

lib_require_venv
lib_activate_venv
lib_ruff_targets

if [[ "${CHECK_ONLY}" == true ]]; then
	if [[ "${GITHUB_OUTPUT}" == true ]]; then
		ruff check "${LIB_RUFF_TARGETS[@]}" --output-format=github
	else
		ruff check "${LIB_RUFF_TARGETS[@]}"
	fi
	ruff format --check "${LIB_RUFF_TARGETS[@]}"
else
	ruff check "${LIB_RUFF_TARGETS[@]}" --fix
	ruff format "${LIB_RUFF_TARGETS[@]}"
fi
