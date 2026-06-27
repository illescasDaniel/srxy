#!/usr/bin/env bash

# Shared helpers for quality gate scripts.

LIB_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_QUALITY_DIR="$(cd "${LIB_SCRIPT_DIR}/.." && pwd)"

lib_find_repo_root() {
	local dir="$1"

	while [[ "${dir}" != "/" ]]; do
		if [[ -f "${dir}/pyproject.toml" ]]; then
			echo "${dir}"
			return 0
		fi
		dir="$(dirname "${dir}")"
	done

	return 1
}

if ! LIB_REPO_ROOT="$(lib_find_repo_root "${LIB_QUALITY_DIR}")"; then
	echo "Could not find project root (pyproject.toml) above ${LIB_QUALITY_DIR}" >&2
	exit 1
fi

lib_has_pytest_tests() {
	local root="${1:-${LIB_REPO_ROOT}}"
	local dir

	if [[ -f "${root}/pyproject.toml" ]] \
		&& grep -qE '(^|[[:space:]"'\''[],])pytest([[:space:]"'\''[],]|$)' "${root}/pyproject.toml" 2>/dev/null; then
		return 0
	fi

	for dir in tests test; do
		if [[ ! -d "${root}/${dir}" ]]; then
			continue
		fi
		if find "${root}/${dir}" \( -name 'test_*.py' -o -name '*_test.py' -o -name 'conftest.py' \) -print -quit | grep -q .; then
			return 0
		fi
		if grep -rlE '(^|[[:space:]])(import pytest|from pytest)' "${root}/${dir}" --include='*.py' 2>/dev/null | grep -q .; then
			return 0
		fi
	done

	return 1
}

lib_require_venv() {
	if [[ ! -d "${LIB_REPO_ROOT}/.venv" ]]; then
		echo "Missing .venv. Create it first: python -m venv .venv && pip install -e '.[dev]'" >&2
		exit 1
	fi
}

lib_activate_venv() {
	cd "${LIB_REPO_ROOT}" || return
	# shellcheck disable=SC1091
	source ".venv/bin/activate"
}

lib_ruff_targets() {
	# shellcheck disable=SC2034  # consumed by callers after sourcing
	LIB_RUFF_TARGETS=()
	if [[ -d "${LIB_REPO_ROOT}/src" ]]; then
		LIB_RUFF_TARGETS+=(src)
	fi
	if [[ -d "${LIB_REPO_ROOT}/tests" ]]; then
		LIB_RUFF_TARGETS+=(tests)
	fi
	if [[ ${#LIB_RUFF_TARGETS[@]} -eq 0 ]]; then
		LIB_RUFF_TARGETS=("${LIB_QUALITY_DIR}/internal")
	fi
}

lib_shell_targets() {
	# shellcheck disable=SC2034  # consumed by callers after sourcing
	mapfile -t LIB_SHELL_TARGETS < <(
		find "${LIB_REPO_ROOT}" -name "*.sh" \
			-not -path "*/.venv/*" \
			-not -path "*/node_modules/*" \
			-not -path "*/templates/*" \
			| sort
	)
}

lib_require_shell_tools() {
	local missing=()
	command -v shellcheck >/dev/null 2>&1 || missing+=("shellcheck")
	command -v shfmt >/dev/null 2>&1 || missing+=("shfmt")
	if [[ "${#missing[@]}" -gt 0 ]]; then
		echo "Missing shell tools: ${missing[*]}" >&2
		echo "Install shellcheck and shfmt via your package manager (e.g. pacman -S shellcheck shfmt)." >&2
		exit 1
	fi
}

lib_pytest_args() {
	# shellcheck disable=SC2034  # LIB_PYTEST_* consumed by pytest.sh after sourcing
	LIB_PYTEST_ARGS=()
	if [[ -d "${LIB_REPO_ROOT}/tests" ]]; then
		LIB_PYTEST_ARGS+=(tests)
	elif [[ -d "${LIB_REPO_ROOT}/test" ]]; then
		LIB_PYTEST_ARGS+=(test)
	fi
	# Local checks.sh runs the full suite; CI runs fast unit tests without optional extras.
	if [[ "${CI:-}" == "true" ]]; then
		LIB_PYTEST_ARGS+=(-m "unit and not semantic and not transcribe")
	fi
	LIB_PYTEST_COV=()
	if [[ -d "${LIB_REPO_ROOT}/src" ]]; then
		# shellcheck disable=SC2034
		LIB_PYTEST_COV=(--cov=src --cov-report=term-missing)
	fi
}
