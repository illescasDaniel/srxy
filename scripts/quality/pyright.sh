#!/usr/bin/env bash

set -euo pipefail

quality_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=internal/lib.sh
source "${quality_dir}/internal/lib.sh"

OUTPUT_JSON=false
for arg in "$@"; do
	case "${arg}" in
	--outputjson)
		OUTPUT_JSON=true
		;;
	esac
done

lib_require_venv
lib_activate_venv
if [[ "${OUTPUT_JSON}" == true ]]; then
	basedpyright --outputjson
else
	basedpyright
fi
