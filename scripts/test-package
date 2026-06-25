#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
venv="${repo_root}/examples/.venv-package-test"
playground="${repo_root}/examples/playground.py"

usage() {
	cat <<'EOF'
Install srxy from PyPI into a fresh venv and run the playground.

Usage: scripts/test-package [options]

Options:
  --testpypi   Install from https://test.pypi.org (deps from production PyPI)
  --no-run     Install only; do not run examples/playground.py
  -h, --help   Show this help
EOF
}

repository="pypi"
run_playground=true

while [[ $# -gt 0 ]]; do
	case "$1" in
	--testpypi)
		repository="testpypi"
		shift
		;;
	--no-run)
		run_playground=false
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

version="$(
	python3 -c "import tomllib; print(tomllib.load(open('${repo_root}/pyproject.toml', 'rb'))['project']['version'])"
)"

if [[ "${repository}" == "testpypi" ]]; then
	index_label="TestPyPI"
	pip_install_args=(
		--index-url https://test.pypi.org/simple/
		--extra-index-url https://pypi.org/simple/
	)
else
	index_label="PyPI"
	pip_install_args=()
fi

echo "Installing srxy==${version} from ${index_label} into ${venv}"

rm -rf "${venv}"
python3 -m venv "${venv}"
"${venv}/bin/pip" install --upgrade pip
"${venv}/bin/pip" install "${pip_install_args[@]}" "srxy==${version}"

"${venv}/bin/python" -c "from srxy import magic_search, search, Q; print('import ok')"

if [[ "${run_playground}" == "true" ]]; then
	echo
	"${venv}/bin/python" "${playground}"
fi
