#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=quality/internal/lib.sh
source "${script_dir}/quality/internal/lib.sh"

usage() {
	cat <<'EOF'
Upload srxy to PyPI (or TestPyPI).

Usage: scripts/upload.sh [options]

Options:
  --testpypi   Upload to https://test.pypi.org instead of https://pypi.org
  --checks     Run the full quality gate before building
  -y, --yes    Pass twine --non-interactive (no credential prompts)
  -h, --help   Show this help

Credentials are read from ~/.pypirc (recommended) or TWINE_USERNAME /
TWINE_PASSWORD. Create a PyPI API token and store it in ~/.pypirc with
chmod 600 before uploading.

Install upload tools: pip install -e ".[uploader]"
EOF
}

repository="pypi"
run_checks=false
twine_yes=false

while [[ $# -gt 0 ]]; do
	case "$1" in
	--testpypi)
		repository="testpypi"
		shift
		;;
	--checks)
		run_checks=true
		shift
		;;
	-y | --yes)
		twine_yes=true
		shift
		;;
	-h | --help)
		usage
		exit 0
		;;
	*)
		echo "error: unknown option: $1" >&2
		usage >&2
		exit 1
		;;
	esac
done

lib_require_venv
lib_activate_venv

if ! python -c "import build, twine" 2>/dev/null; then
	echo "error: missing upload dependencies; run: pip install -e '.[uploader]'" >&2
	exit 1
fi

pypirc="${HOME}/.pypirc"
if [[ ! -f "${pypirc}" && -z "${TWINE_PASSWORD:-}" ]]; then
	echo "warning: no ${pypirc} and TWINE_PASSWORD is unset; twine will prompt for credentials" >&2
elif [[ -f "${pypirc}" ]]; then
	pypirc_mode="$(stat -c '%a' "${pypirc}" 2>/dev/null || stat -f '%OLp' "${pypirc}")"
	if [[ "${pypirc_mode}" != "600" ]]; then
		echo "warning: ${pypirc} permissions are ${pypirc_mode}; chmod 600 is recommended" >&2
	fi
fi

if [[ "${run_checks}" == "true" ]]; then
	"${script_dir}/quality/checks.sh"
fi

rm -rf "${LIB_REPO_ROOT}/dist"
python -m build
python -m twine check "${LIB_REPO_ROOT}"/dist/*

twine_args=()
if [[ "${twine_yes}" == "true" ]]; then
	twine_args+=(--non-interactive)
fi
if [[ "${repository}" == "testpypi" ]]; then
	twine_args+=(--repository testpypi)
fi

python -m twine upload "${twine_args[@]}" "${LIB_REPO_ROOT}"/dist/*
