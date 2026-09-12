#!/usr/bin/env bash

set -u

# Quality gate — ruff, shell, ty, pip-audit, build, and optionally pytest.
# --fix: ruff autofix+format and shfmt write; sequential (writers first).
# Without --fix: light verify steps run in parallel, overlapping pytest buckets
# (core/gui/tui/heavy) selected via --scope / auto git-diff scope.
# Only one gate at a time (flock).

quality_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
internal_dir="${quality_dir}/internal"

# shellcheck source=internal/gate.sh
source "${internal_dir}/gate.sh"

# shellcheck source=internal/lib.sh
source "${internal_dir}/lib.sh"

lib_gate_setup_interrupt_traps

# Exclusive lock so overlapping agent/manual gates cannot spawn multiple -n N pytest trees.
# Keep the lock outside .venv — that tree is often cursorignored / RO in agent sandboxes.
GATE_LOCK_FILE="${LIB_REPO_ROOT}/.srxy-quality-gate.lock"
exec 200>>"${GATE_LOCK_FILE}"
if ! flock -n 200; then
	lib_gate_print_lock_holder "${GATE_LOCK_FILE}"
	exit 1
fi
export LIB_GATE_LOCK_FILE="${GATE_LOCK_FILE}"
export LIB_GATE_LOCK_MAIN_PID="$$"
export LIB_GATE_LOCK_SCRIPT="checks.sh"
LIB_GATE_LOCK_STARTED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
export LIB_GATE_LOCK_STARTED
lib_gate_write_lock_file running

FIX=false
FULL=false
FULL_CPU=false
QUIET=false
TIMINGS=false
NO_CACHE=false
SCOPE="auto"
SCOPE_SET=false

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
	--quiet)
		QUIET=true
		;;
	--timings)
		TIMINGS=true
		;;
	--no-cache)
		NO_CACHE=true
		;;
	--all)
		SCOPE="all"
		SCOPE_SET=true
		;;
	--core)
		if [[ "${SCOPE_SET}" == true && "${SCOPE}" != "auto" ]]; then
			SCOPE="${SCOPE},core"
		else
			SCOPE="core"
			SCOPE_SET=true
		fi
		;;
	--cli)
		if [[ "${SCOPE_SET}" == true && "${SCOPE}" != "auto" ]]; then
			SCOPE="${SCOPE},cli"
		else
			SCOPE="cli"
			SCOPE_SET=true
		fi
		;;
	--tui)
		if [[ "${SCOPE_SET}" == true && "${SCOPE}" != "auto" ]]; then
			SCOPE="${SCOPE},tui"
		else
			SCOPE="tui"
			SCOPE_SET=true
		fi
		;;
	--gui)
		if [[ "${SCOPE_SET}" == true && "${SCOPE}" != "auto" ]]; then
			SCOPE="${SCOPE},gui"
		else
			SCOPE="gui"
			SCOPE_SET=true
		fi
		;;
	--scope=*)
		SCOPE="${arg#--scope=}"
		SCOPE_SET=true
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

if [[ "${FULL}" == true && "${SCOPE_SET}" != true ]]; then
	SCOPE="all"
fi

export LIB_PYTEST_FULL="${FULL}"
export LIB_PYTEST_FULL_CPU="${FULL_CPU}"
export LIB_GATE_QUIET="${QUIET}"
export LIB_GATE_TIMINGS="${TIMINGS}"
export LIB_GATE_NO_CACHE="${NO_CACHE}"
export LIB_GATE_SCOPE="${SCOPE}"

lib_resolve_buckets
echo "scope: ${LIB_SELECTED_BUCKETS[*]} (${LIB_SCOPE_REASON})"

HAS_PYTEST=false
if lib_has_pytest_tests "${LIB_REPO_ROOT}"; then
	HAS_PYTEST=true
fi

GATE_PLANNED_STEPS=5
if [[ "${HAS_PYTEST}" == true ]]; then
	# shellcheck disable=SC2034
	GATE_PLANNED_STEPS=$((5 + ${#LIB_SELECTED_BUCKETS[@]}))
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

gate_step_ty() {
	ty_stderr="$(mktemp)"
	ty_out="$("${quality_dir}/ty.sh" --github 2>"${ty_stderr}")"
	ty_exit=$?
	emit_out="$(printf '%s' "${ty_out}" | lib_uv_run python "${internal_dir}/gate_emit.py" ty 2>&1)"
	summary=""
	while IFS= read -r line; do
		if [[ "${line}" == GATE_SUMMARY* ]]; then
			summary="${line}"
		elif [[ "${line}" == ::* ]]; then
			echo "${line}"
		fi
	done <<<"${emit_out}"
	if [[ -s "${ty_stderr}" ]] && [[ "${ty_exit}" -ne 0 ]] && [[ -z "${summary}" ]]; then
		cat "${ty_stderr}" >&2
	fi
	rm -f "${ty_stderr}"
	if [[ -n "${summary}" ]]; then
		gate_apply_emit_summary "${summary}"
	else
		if [[ "${ty_exit}" -eq 0 ]]; then
			gate_record_pass
		else
			gate_gha_error "" "" "" "ty" "type check failed (exit ${ty_exit})"
			gate_record_fail 1 0
		fi
	fi
}

gate_step_pip_audit() {
	local lock_hash=""
	if [[ -f "${LIB_REPO_ROOT}/uv.lock" ]]; then
		lock_hash="$(lib_hash_file "${LIB_REPO_ROOT}/uv.lock")"
		if lib_cache_hit "pip-audit" "${lock_hash}" 7; then
			echo "note: skipping pip-audit (uv.lock unchanged, cache hit)"
			gate_emit_result "skip" 0 0
			return 0
		fi
	fi
	audit_output="$("${internal_dir}/audit_deps.sh" 2>&1)"
	audit_exit=$?
	printf '%s\n' "${audit_output}"
	if [[ "${audit_exit}" -eq 0 ]]; then
		if [[ -n "${lock_hash}" ]]; then
			lib_cache_store "pip-audit" "${lock_hash}"
		fi
		gate_record_pass
	else
		gate_gha_error "" "" "" "pip-audit" "dependency audit failed (exit ${audit_exit})"
		gate_add_detail "[pip-audit] exit ${audit_exit}"
		gate_record_fail 1 0
	fi
}

gate_step_build() {
	local build_hash=""
	if [[ -f "${LIB_REPO_ROOT}/pyproject.toml" ]]; then
		# Hash packaging inputs (pyproject + tracked src file list).
		build_hash="$({
			lib_hash_file "${LIB_REPO_ROOT}/pyproject.toml"
			find "${LIB_REPO_ROOT}/src" -type f 2>/dev/null | sort | while read -r f; do
				lib_hash_file "${f}"
			done
		} | "$(lib_python)" -c 'import hashlib,sys; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())')"
		if lib_cache_hit "build" "${build_hash}" 7; then
			echo "note: skipping wheel build (packaging inputs unchanged, cache hit)"
			gate_emit_result "skip" 0 0
			return 0
		fi
	fi
	export UV_NO_SYNC=1
	build_output="$("${quality_dir}/build.sh" 2>&1)"
	build_exit=$?
	printf '%s\n' "${build_output}"
	if [[ "${build_exit}" -eq 0 ]]; then
		if [[ -n "${build_hash}" ]]; then
			lib_cache_store "build" "${build_hash}"
		fi
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
	local pid

	(
		export GATE_STATUS_FILE="${log_dir}/${name}.status"
		rm -f "${GATE_STATUS_FILE}" "${GATE_STATUS_FILE}.details"
		"${fn}" >"${log_dir}/${name}.log" 2>&1
	) &
	pid=$!
	lib_gate_track_pid "${pid}"
}

gate_finish_step() {
	local name="$1"
	local log_dir="$2"

	gate_step_start "${name}"
	unset GATE_STATUS_FILE
	gate_load_result "${log_dir}/${name}.status"
	if [[ "${LIB_GATE_QUIET:-false}" != true || "${GATE_STEP_STATUS[GATE_CURRENT_INDEX]}" == "FAIL" ]]; then
		if [[ -f "${log_dir}/${name}.log" ]]; then
			cat "${log_dir}/${name}.log"
		fi
	fi
}

if [[ "${FIX}" == true ]]; then
	gate_step_start "ruff"
	gate_step_ruff

	gate_step_start "shell"
	gate_step_shell

	gate_step_start "ty"
	gate_step_ty

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
	cleanup_parallel_dir() {
		if [[ -n "${parallel_dir:-}" && -d "${parallel_dir}" ]]; then
			rm -rf "${parallel_dir}"
		fi
	}
	lib_gate_add_cleanup cleanup_parallel_dir

	if [[ -z "${LIB_PYTEST_WORKERS:-}" ]]; then
		LIB_PYTEST_WORKERS="$(_lib_pytest_worker_count)"
		export LIB_PYTEST_WORKERS
	fi

	echo "Parallel verify (light steps overlapping pytest buckets; workers=${LIB_PYTEST_WORKERS})"

	set -m
	# Overlap pytest with light steps; tee streams bucket progress to the terminal.
	pytest_pid=""
	if [[ "${HAS_PYTEST}" == true ]]; then
		(
			export GATE_STATUS_FILE="${parallel_dir}/pytest.status"
			rm -f "${GATE_STATUS_FILE}" "${GATE_STATUS_FILE}.details"
			gate_step_pytest 2>&1 | tee "${parallel_dir}/pytest.log"
		) &
		pytest_pid=$!
		lib_gate_track_pid "${pytest_pid}"
	fi

	gate_run_step_logged "ruff" gate_step_ruff "${parallel_dir}"
	gate_run_step_logged "shell" gate_step_shell "${parallel_dir}"
	gate_run_step_logged "ty" gate_step_ty "${parallel_dir}"
	gate_run_step_logged "pip-audit" gate_step_pip_audit "${parallel_dir}"
	gate_run_step_logged "build" gate_step_build "${parallel_dir}"
	set +m
	wait

	gate_finish_step "ruff" "${parallel_dir}"
	gate_finish_step "shell" "${parallel_dir}"
	gate_finish_step "ty" "${parallel_dir}"
	gate_finish_step "pip-audit" "${parallel_dir}"
	gate_finish_step "build" "${parallel_dir}"

	if [[ -n "${pytest_pid}" ]]; then
		wait "${pytest_pid}" 2>/dev/null || true
		gate_finish_step "pytest" "${parallel_dir}"
	fi
	rm -rf "${parallel_dir}"
fi

gate_exit
