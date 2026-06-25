#!/usr/bin/env bash

set -euo pipefail

quality_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=internal/lib.sh
source "${quality_dir}/internal/lib.sh"

lib_require_venv
lib_activate_venv

build_dir="$(mktemp -d)"
cleanup() {
	rm -rf "${build_dir}"
}
trap cleanup EXIT

pip wheel --no-deps -w "${build_dir}" .

wheel_count=0
while IFS= read -r _; do
	wheel_count=$((wheel_count + 1))
done < <(find "${build_dir}" -name '*.whl' -type f)

if [[ "${wheel_count}" -eq 0 ]]; then
	echo "No wheel produced in ${build_dir}" >&2
	exit 1
fi

echo "Built ${wheel_count} wheel(s):"
find "${build_dir}" -name '*.whl' -type f -print
