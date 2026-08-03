#!/usr/bin/env bash

set -u

# Quality gate — ruff, shell, basedpyright, pip-audit, build, and optionally pytest.
# --fix: ruff autofix+format and shfmt write; sequential (writers first).
# Without --fix: light verify steps run in parallel, then pytest alone (safe
# parallel unit subset, then serial heavy semantic/transcribe/gui/tui/integration).
# Only one gate at a time (flock).

quality_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
internal_dir="${quality_dir}/internal"

# shellcheck source=internal/gate.sh
source "${internal_dir}/gate.sh"

# shellcheck source=internal/lib.sh
source "${internal_dir}/lib.sh"

# Exclusive lock so overlapping agent/manual gates cannot spawn multiple -n N pytest trees.
# Keep the lock outside .venv — that tree is often cursorignored / RO in agent sandboxes.
GATE_LOCK_FILE="${LIB_REPO_ROOT}/.srxy-quality-gate.lock"
exec 200>"${GATE_LOCK_FILE}"
if ! flock -n 200; then
	echo "error: another quality gate is already running (lock: ${GATE_LOCK_FILE})." >&2
	echo "Stop leftover checks.sh / pytest processes for this repo, then retry." >&2
	exit 1
fi

FIX=false
FULL=false
FULL_CPU=false
for arg in "$@"; do
	case "${arg}" in
	--fix)
		FIX=true
		;;
	--full)
		FULL=true
		;;
	--full+cpu)
		FULL=true
		FULL_CPU=true
		;;
	esac
done

if [[ "${CI:-}" == "true" && "${FIX}" == true ]]; then
	echo "note: --fix ignored in CI (check-only mode)"
	FIX=false
fi

if [[ "${CI:-}" == "true" && ("${FULL}" == true || "${FULL_CPU}" == true) ]]; then
	echo "note: --full/--full+cpu ignored in CI"
	FULL=false
	FULL_CPU=false
fi

export LIB_PYTEST_FULL="${FULL}"
export LIB_PYTEST_FULL_CPU="${FULL_CPU}"

HAS_PYTEST=false
if lib_has_pytest_tests "${LIB_REPO_ROOT}"; then
	HAS_PYTEST=true
fi

GATE_PLANNED_STEPS=5
if [[ "${HAS_PYTEST}" == true ]]; then
	# shellcheck disable=SC2034
	GATE_PLANNED_STEPS=6
fi
gate_init
lib_require_venv
cd "${LIB_REPO_ROOT}" || exit

set +e

gate_step_ruff() {
	if [[ "${FIX}" == true ]]; then
		ruff_output="$("${quality_dir}/ruff.sh" 2>&1)"
		ruff_exit=$?
		printf '%s\n' "${ruff_output}"
		if [[ "${ruff_exit}" -eq 0 ]]; then
			gate_record_pass
		else
			gate_gha_error "" "" "" "ruff" "ruff fix/format failed (exit ${ruff_exit})"
			gate_add_detail "[ruff] exit ${ruff_exit}"
			gate_record_fail 1 0
		fi
		return 0
	fi

	lib_ruff_targets
	ruff_check_out="$(lib_uv_run ruff check "${LIB_RUFF_TARGETS[@]}" --output-format=github 2>&1)"
	printf '%s\n' "${ruff_check_out}"
	emit_out="$(printf '%s\n' "${ruff_check_out}" | lib_uv_run python "${internal_dir}/gate_emit.py" ruff-github 2>&1)"
	summary=""
	while IFS= read -r line; do
		if [[ "${line}" == GATE_SUMMARY* ]]; then
			summary="${line}"
		fi
	done <<<"${emit_out}"
	ruff_format_out="$(lib_uv_run ruff format --check "${LIB_RUFF_TARGETS[@]}" 2>&1)"
	ruff_format_exit=$?
	if [[ -n "${ruff_format_out}" ]]; then
		printf '%s\n' "${ruff_format_out}"
	fi
	ruff_errors=0
	ruff_warnings=0
	if [[ -n "${summary}" ]]; then
		ruff_errors="$(echo "${summary}" | sed -n 's/.*errors=\([0-9]*\).*/\1/p')"
		ruff_warnings="$(echo "${summary}" | sed -n 's/.*warnings=\([0-9]*\).*/\1/p')"
	fi
	if [[ "${ruff_format_exit}" -ne 0 ]]; then
		ruff_errors=$((ruff_errors + 1))
		gate_gha_error "" "" "" "ruff" "format check failed"
		gate_add_detail "[ruff] format check failed"
	fi
	if [[ "${ruff_errors}" -gt 0 || "${ruff_format_exit}" -ne 0 ]]; then
		gate_record_fail "${ruff_errors:-1}" "${ruff_warnings:-0}"
	elif [[ "${ruff_warnings:-0}" -gt 0 ]]; then
		gate_emit_result "warn" 0 "${ruff_warnings}"
	else
		gate_record_pass
	fi
}

gate_step_shell() {
	if [[ "${FIX}" == true ]]; then
		shell_output="$("${quality_dir}/shellcheck.sh" --fix 2>&1)"
	else
		shell_output="$("${quality_dir}/shellcheck.sh" 2>&1)"
	fi
	shell_exit=$?
	printf '%s\n' "${shell_output}"
	if [[ "${shell_exit}" -eq 0 ]]; then
		gate_record_pass
	else
		gate_gha_error "" "" "" "shell" "shell lint/format failed (exit ${shell_exit})"
		gate_add_detail "[shell] exit ${shell_exit}"
		gate_record_fail 1 0
	fi
}

gate_step_pyright() {
	pyright_stderr="$(mktemp)"
	pyright_json="$("${quality_dir}/pyright.sh" --outputjson 2>"${pyright_stderr}")"
	pyright_exit=$?
	emit_out="$(printf '%s' "${pyright_json}" | lib_uv_run python "${internal_dir}/gate_emit.py" pyright 2>&1)"
	summary=""
	while IFS= read -r line; do
		if [[ "${line}" == GATE_SUMMARY* ]]; then
			summary="${line}"
		elif [[ "${line}" == ::* ]]; then
			echo "${line}"
			if [[ "${line}" == *"basedpyright returned invalid JSON"* ]] && [[ -s "${pyright_stderr}" ]]; then
				cat "${pyright_stderr}" >&2
			fi
		fi
	done <<<"${emit_out}"
	rm -f "${pyright_stderr}"
	if [[ -n "${summary}" ]]; then
		gate_apply_emit_summary "${summary}"
	else
		if [[ "${pyright_exit}" -eq 0 ]]; then
			gate_record_pass
		else
			gate_gha_error "" "" "" "basedpyright" "type check failed (exit ${pyright_exit})"
			gate_record_fail 1 0
		fi
	fi
}

gate_step_pip_audit() {
	audit_output="$("${internal_dir}/audit_deps.sh" 2>&1)"
	audit_exit=$?
	printf '%s\n' "${audit_output}"
	if [[ "${audit_exit}" -eq 0 ]]; then
		gate_record_pass
	else
		gate_gha_error "" "" "" "pip-audit" "dependency audit failed (exit ${audit_exit})"
		gate_add_detail "[pip-audit] exit ${audit_exit}"
		gate_record_fail 1 0
	fi
}

gate_step_build() {
	build_output="$("${quality_dir}/build.sh" 2>&1)"
	build_exit=$?
	printf '%s\n' "${build_output}"
	if [[ "${build_exit}" -eq 0 ]]; then
		gate_record_pass
	else
		gate_gha_error "" "" "" "build" "package build failed (exit ${build_exit})"
		gate_add_detail "[build] exit ${build_exit}"
		gate_record_fail 1 0
	fi
}

gate_step_pytest() {
	# Always stream live — never buffer until EOF (looks hung under CI=true / agents).
	"${quality_dir}/pytest.sh"
	pytest_exit=$?
	if [[ "${pytest_exit}" -eq 0 ]]; then
		gate_record_pass
	else
		gate_gha_error "" "" "" "pytest" "tests failed (exit ${pytest_exit})"
		gate_add_detail "[pytest] exit ${pytest_exit}"
		gate_record_fail 1 0
	fi
}

gate_run_step_logged() {
	local name="$1"
	local fn="$2"
	local log_dir="$3"

	(
		export GATE_STATUS_FILE="${log_dir}/${name}.status"
		rm -f "${GATE_STATUS_FILE}" "${GATE_STATUS_FILE}.details"
		"${fn}" >"${log_dir}/${name}.log" 2>&1
	) &
}

gate_finish_step() {
	local name="$1"
	local log_dir="$2"

	gate_step_start "${name}"
	if [[ -f "${log_dir}/${name}.log" ]]; then
		cat "${log_dir}/${name}.log"
	fi
	unset GATE_STATUS_FILE
	gate_load_result "${log_dir}/${name}.status"
}

if [[ "${FIX}" == true ]]; then
	gate_step_start "ruff"
	gate_step_ruff

	gate_step_start "shell"
	gate_step_shell

	gate_step_start "basedpyright"
	gate_step_pyright

	gate_step_start "pip-audit"
	gate_step_pip_audit

	gate_step_start "build"
	gate_step_build

	if [[ "${HAS_PYTEST}" == true ]]; then
		gate_step_start "pytest"
		gate_step_pytest
	fi
else
	parallel_dir="$(mktemp -d "${TMPDIR:-/tmp}/srxy-gate.XXXXXX")"
	# Cap xdist fan-out (torch/Qt-heavy work runs serially in pytest.sh).
	# Respect an explicit LIB_PYTEST_WORKERS override from the environment.
	if [[ -z "${LIB_PYTEST_WORKERS:-}" ]]; then
		workers="$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 2)"
		if [[ "${workers}" -lt 1 ]]; then
			workers=1
		fi
		if [[ "${workers}" -gt 4 ]]; then
			workers=4
		fi
		export LIB_PYTEST_WORKERS="${workers}"
	fi

	echo "Parallel verify (light steps; then pytest -n ${LIB_PYTEST_WORKERS}, heavy serial)"

	gate_run_step_logged "ruff" gate_step_ruff "${parallel_dir}"
	gate_run_step_logged "shell" gate_step_shell "${parallel_dir}"
	gate_run_step_logged "basedpyright" gate_step_pyright "${parallel_dir}"
	gate_run_step_logged "pip-audit" gate_step_pip_audit "${parallel_dir}"
	gate_run_step_logged "build" gate_step_build "${parallel_dir}"
	wait

	gate_finish_step "ruff" "${parallel_dir}"
	gate_finish_step "shell" "${parallel_dir}"
	gate_finish_step "basedpyright" "${parallel_dir}"
	gate_finish_step "pip-audit" "${parallel_dir}"
	gate_finish_step "build" "${parallel_dir}"

	# Pytest after the light steps so xdist workers are not fighting torch/pyright.
	if [[ "${HAS_PYTEST}" == true ]]; then
		gate_step_start "pytest"
		gate_step_pytest
	fi
	rm -rf "${parallel_dir}"
fi

gate_exit
