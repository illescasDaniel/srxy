#!/usr/bin/env bash

set -euo pipefail

# Run selected pytest buckets (core/gui/tui/heavy). Invoked by checks.sh.
# LIB_GATE_SCOPE / LIB_SELECTED_BUCKETS may already be set by the parent gate.

quality_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=internal/lib.sh
source "${quality_dir}/internal/lib.sh"
# shellcheck source=internal/run_with_watch.sh
source "${quality_dir}/internal/run_with_watch.sh"

lib_require_venv

if [[ "${CI:-}" == "true" ]]; then
	: "${LIB_PYTEST_WALL_SECONDS:=300}"
	: "${LIB_PYTEST_STALL_SECONDS:=120}"
elif [[ "${LIB_PYTEST_FULL:-}" == "true" ]]; then
	: "${LIB_PYTEST_WALL_SECONDS:=1800}"
	: "${LIB_PYTEST_STALL_SECONDS:=180}"
else
	: "${LIB_PYTEST_WALL_SECONDS:=600}"
	: "${LIB_PYTEST_STALL_SECONDS:=120}"
fi

export PYTHONUNBUFFERED=1
if [[ -n "${SRXY_PYTEST_PYTHONPATH:-}" ]]; then
	export PYTHONPATH="${SRXY_PYTEST_PYTHONPATH}${PYTHONPATH:+:${PYTHONPATH}}"
fi

quiet_args=()
if [[ "${LIB_GATE_QUIET:-false}" == "true" ]]; then
	quiet_args=(-q --no-header -ra --tb=short -p agent_progress)
	export PYTHONPATH="${quality_dir}/internal${PYTHONPATH:+:${PYTHONPATH}}"
fi

if [[ -z "${LIB_SELECTED_BUCKETS[*]:-}" ]]; then
	lib_resolve_buckets
fi

echo "pytest buckets: ${LIB_SELECTED_BUCKETS[*]} (${LIB_SCOPE_REASON:-})"

cd "${LIB_REPO_ROOT}" || exit 1
pytest_bin=("${LIB_REPO_ROOT}/.venv/bin/python" -m pytest)

serialize="${LIB_GATE_BUCKET_CONCURRENCY:-}"
if [[ "${serialize}" == "1" ]]; then
	echo "note: LIB_GATE_BUCKET_CONCURRENCY=1 — buckets run serially"
fi

run_one_bucket() {
	local bucket="$1"
	local log_file="${2:-}"
	local env_pair
	local -a cmd_env=()

	lib_bucket_args "${bucket}"
	if [[ ${#LIB_BUCKET_ARGS[@]} -eq 0 ]]; then
		echo "pytest[${bucket}]: skipped (no paths)"
		return 0
	fi

	for env_pair in "${LIB_BUCKET_ENV[@]:-}"; do
		cmd_env+=("${env_pair}")
	done
	if [[ "${LIB_GATE_QUIET:-false}" == "true" && "${bucket}" == "heavy" ]]; then
		cmd_env+=(
			LIB_PYTEST_PROGRESS_INTERVAL=1
			HF_HUB_DISABLE_PROGRESS_BARS=1
			TRANSFORMERS_VERBOSITY=error
			TQDM_DISABLE=1
		)
	fi

	echo "pytest[${bucket}]: args: ${LIB_BUCKET_ARGS[*]}"
	echo "pytest[${bucket}]: env: ${cmd_env[*]:-}"

	local -a run_cmd=()
	if [[ ${#cmd_env[@]} -gt 0 ]]; then
		run_cmd=(env "${cmd_env[@]}" "${pytest_bin[@]}" "${LIB_BUCKET_ARGS[@]}")
	else
		run_cmd=("${pytest_bin[@]}" "${LIB_BUCKET_ARGS[@]}")
	fi
	run_cmd+=(${quiet_args[@]+"${quiet_args[@]}"})

	if [[ -n "${log_file}" ]]; then
		lib_run_with_watch "${LIB_PYTEST_WALL_SECONDS}" "${LIB_PYTEST_STALL_SECONDS}" -- \
			"${run_cmd[@]}" >"${log_file}" 2>&1
	else
		lib_run_with_watch "${LIB_PYTEST_WALL_SECONDS}" "${LIB_PYTEST_STALL_SECONDS}" -- \
			"${run_cmd[@]}"
	fi
}

# Longest-job-first concurrent (or serial) execution.
bucket_list=("${LIB_SELECTED_BUCKETS[@]}")
bucket_count="${#bucket_list[@]}"
overall_exit=0
tmp_dir=""

cleanup_tmp() {
	if [[ -n "${tmp_dir}" && -d "${tmp_dir}" ]]; then
		rm -rf "${tmp_dir}"
	fi
}
trap cleanup_tmp EXIT

if [[ "${serialize}" == "1" || "${bucket_count}" -eq 1 ]]; then
	for bucket in "${bucket_list[@]}"; do
		set +e
		run_one_bucket "${bucket}"
		code=$?
		set -e
		if [[ "${code}" -ne 0 ]]; then
			overall_exit="${code}"
			break
		fi
	done
else
	tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/srxy-pytest.XXXXXX")"
	export LIB_GATE_ACTIVE_BUCKETS="${bucket_count}"
	pids=()
	logs=()
	for bucket in "${bucket_list[@]}"; do
		log="${tmp_dir}/${bucket}.log"
		logs+=("${log}")
		(
			run_one_bucket "${bucket}" "${log}"
		) &
		pids+=($!)
	done
	i=0
	for bucket in "${bucket_list[@]}"; do
		set +e
		wait "${pids[i]}"
		code=$?
		set -e
		echo ""
		echo "──── pytest[${bucket}] (exit ${code}) ────"
		cat "${logs[i]}"
		if [[ "${code}" -ne 0 && "${overall_exit}" -eq 0 ]]; then
			overall_exit="${code}"
		fi
		i=$((i + 1))
	done
fi

exit "${overall_exit}"
