#!/usr/bin/env bash

set -euo pipefail

quality_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=internal/lib.sh
source "${quality_dir}/internal/lib.sh"

OUTPUT_GITHUB=false
for arg in "$@"; do
	case "${arg}" in
	--output-format=github | --github)
		OUTPUT_GITHUB=true
		;;
	esac
done

lib_require_venv
if [[ "${OUTPUT_GITHUB}" == true ]]; then
	lib_uv_run ty check --output-format github
else
	lib_uv_run ty check
fi
