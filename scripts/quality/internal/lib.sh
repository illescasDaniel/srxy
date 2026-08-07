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
		echo "Missing .venv. Create it first: uv sync --extra semantic" >&2
		exit 1
	fi
}

lib_uv_run() {
	cd "${LIB_REPO_ROOT}" || return
	uv run -- "$@"
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

_lib_find_shell_scripts() {
	find "${LIB_REPO_ROOT}" -name "*.sh" \
		-not -path "*/.venv/*" \
		-not -path "*/node_modules/*" \
		-not -path "*/templates/*" \
		-not -path "*/dist/*" \
		| sort
}

lib_shell_targets() {
	# shellcheck disable=SC2034  # consumed by callers after sourcing
	LIB_SHELL_TARGETS=()
	# mapfile needs Bash 4+. macOS still ships /bin/bash 3.2 (even when your login shell is zsh).
	if ((BASH_VERSINFO[0] >= 4)); then
		mapfile -t LIB_SHELL_TARGETS < <(_lib_find_shell_scripts)
	else
		local line
		while IFS= read -r line; do
			LIB_SHELL_TARGETS+=("${line}")
		done < <(_lib_find_shell_scripts)
	fi
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

# Parallelize only suites that stay safe under xdist. Torch/whisper/Qt/OCR-heavy
# markers run serially via lib_pytest_heavy_args (see pytest.sh).
_lib_pytest_safe_marker() {
	if [[ "${CI:-}" == "true" ]]; then
		# CI keeps unit+gui (+ocr) parallel; no serial follow-up under CI=true.
		echo "(unit or gui) and not integration and not semantic and not transcribe"
	else
		# Local: OCR orientation probes thrash tesseract under xdist (timeouts/OOM).
		echo "unit and not semantic and not transcribe and not gui and not tui and not integration and not ocr"
	fi
}

_lib_pytest_heavy_marker() {
	if [[ "${LIB_PYTEST_FULL:-}" == "true" ]]; then
		echo "semantic or transcribe or gui or tui or integration or ocr or integration_full or transcribe_device_matrix"
	else
		echo "(semantic or transcribe or gui or tui or integration or ocr) and not integration_full and not transcribe_device_matrix"
	fi
}

_lib_pytest_worker_count() {
	local n
	if [[ -n "${LIB_PYTEST_WORKERS:-}" ]]; then
		echo "${LIB_PYTEST_WORKERS}"
		return
	fi
	n="$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 2)"
	if [[ "${n}" -lt 1 ]]; then
		n=1
	fi
	# Cap fan-out everywhere (incl. local CI=true mimics). GitHub runners are
	# typically ≤4 cores; higher local counts crash Qt/torch workers.
	if [[ "${n}" -gt 4 ]]; then
		n=4
	fi
	echo "${n}"
}

lib_pytest_args() {
	# shellcheck disable=SC2034  # LIB_PYTEST_* consumed by pytest.sh after sourcing
	LIB_PYTEST_ARGS=()
	if [[ -d "${LIB_REPO_ROOT}/tests" ]]; then
		LIB_PYTEST_ARGS+=(tests)
	elif [[ -d "${LIB_REPO_ROOT}/test" ]]; then
		LIB_PYTEST_ARGS+=(test)
	fi
	LIB_PYTEST_ARGS+=(-m "$(_lib_pytest_safe_marker)")
	# max-worker-restart=0: fail fast on crashed workers (Qt/native) instead of
	# hanging while xdist replaces the node ("Not properly terminated").
	LIB_PYTEST_ARGS+=(-n "$(_lib_pytest_worker_count)" --dist=loadgroup --max-worker-restart=0)
	# Change-aware selection for local day-to-day gate only (not CI, not --full).
	if [[ "${CI:-}" != "true" && "${LIB_PYTEST_FULL:-}" != "true" ]]; then
		LIB_PYTEST_ARGS+=(--testmon-forceselect --ff)
	fi
	LIB_PYTEST_COV=()
	# Coverage only on --full / --full+cpu (avoids clash with testmon collection).
	if [[ "${LIB_PYTEST_FULL:-}" == "true" && -d "${LIB_REPO_ROOT}/src" ]]; then
		# skip-covered keeps the report short so FAILURES / -ra stay on screen.
		# shellcheck disable=SC2034
		LIB_PYTEST_COV=(--cov=src --cov-report=term-missing:skip-covered -ra --tb=short)
	fi
}

lib_pytest_heavy_args() {
	# shellcheck disable=SC2034  # consumed by pytest.sh after sourcing
	LIB_PYTEST_HEAVY_ARGS=()
	# CI already excludes heavy markers from the parallel pass; no serial follow-up.
	if [[ "${CI:-}" == "true" ]]; then
		return 0
	fi
	if [[ -d "${LIB_REPO_ROOT}/tests" ]]; then
		LIB_PYTEST_HEAVY_ARGS+=(tests)
	elif [[ -d "${LIB_REPO_ROOT}/test" ]]; then
		LIB_PYTEST_HEAVY_ARGS+=(test)
	fi
	LIB_PYTEST_HEAVY_ARGS+=(-m "$(_lib_pytest_heavy_marker)" -n 0)
	if [[ "${LIB_PYTEST_FULL_CPU:-}" == "true" ]]; then
		LIB_PYTEST_HEAVY_ARGS+=(--integration-test-cpu)
	fi
	LIB_PYTEST_HEAVY_COV=()
	if [[ "${LIB_PYTEST_FULL:-}" == "true" && -d "${LIB_REPO_ROOT}/src" ]]; then
		# Append so coverage from the safe parallel pass is not wiped.
		# shellcheck disable=SC2034
		LIB_PYTEST_HEAVY_COV=(--cov=src --cov-append --cov-report=term-missing:skip-covered -ra --tb=short)
	fi
}
