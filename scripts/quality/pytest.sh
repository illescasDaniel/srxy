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
lib_gate_setup_interrupt_traps

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

lib_pytest_progress_interval() {
	echo "${LIB_PYTEST_PROGRESS_INTERVAL:-25}"
}

# Emit new [gate] progress lines from a bucket log (quiet parallel mode).
# $3 = name of offsets array; $4 = index into that array (byte cursor per bucket).
lib_pytest_emit_log_gate_lines() {
	local bucket="$1"
	local log="$2"
	local -n _offsets=$3
	local idx="$4"

	[[ -f "${log}" ]] || return 0
	local size
	size="$(wc -c <"${log}" | tr -d ' ')"
	if [[ "${size}" -le "${_offsets[idx]}" ]]; then
		return 0
	fi
	tail -c +"$((_offsets[idx] + 1))" "${log}" | while IFS= read -r line || [[ -n "${line}" ]]; do
		if [[ "${line}" == \[gate\]* ]]; then
			printf '%s\n' "${line}"
		fi
	done
	_offsets[idx]="${size}"
}

# Wait for parallel bucket jobs; stream sparse progress while they run.
lib_pytest_wait_parallel_buckets() {
	local -n _pids=$1
	local -n _logs=$2
	local -n _buckets=$3
	local -n _overall_ref=$4

	local count="${#_pids[@]}"
	local interval now last_heartbeat start_epoch
	local -a offsets=()
	local -a done_flags=()
	local i pid bucket log code elapsed

	interval="$(lib_pytest_progress_interval)"
	start_epoch="$(date +%s)"
	last_heartbeat=0

	for ((i = 0; i < count; i++)); do
		# shellcheck disable=SC2034  # offsets mutated via nameref in lib_pytest_emit_log_gate_lines
		offsets[i]=0
		done_flags[i]=0
	done

	while true; do
		local finished=0
		local any_running=false
		now="$(date +%s)"

		for ((i = 0; i < count; i++)); do
			if [[ "${done_flags[i]}" -eq 1 ]]; then
				finished=$((finished + 1))
				continue
			fi

			pid="${_pids[i]}"
			bucket="${_buckets[i]}"
			log="${_logs[i]}"

			if [[ "${LIB_GATE_QUIET:-false}" == true ]]; then
				lib_pytest_emit_log_gate_lines "${bucket}" "${log}" offsets "${i}"
			fi

			if ! kill -0 "${pid}" 2>/dev/null; then
				set +e
				wait "${pid}"
				code=$?
				set -e
				done_flags[i]=1
				finished=$((finished + 1))

				if [[ "${LIB_GATE_QUIET:-false}" == true ]]; then
					lib_pytest_emit_log_gate_lines "${bucket}" "${log}" offsets "${i}"
				fi

				echo ""
				echo "──── pytest[${bucket}] (exit ${code}) ────"
				if [[ "${code}" -ne 0 || "${LIB_GATE_QUIET:-false}" != true ]]; then
					cat "${log}"
				fi
				if [[ "${code}" -ne 0 && "${_overall_ref}" -eq 0 ]]; then
					_overall_ref="${code}"
				fi
				continue
			fi

			any_running=true
		done

		if [[ "${finished}" -ge "${count}" ]]; then
			break
		fi

		if [[ "${any_running}" == true && $((now - last_heartbeat)) -ge interval ]]; then
			elapsed=$((now - start_epoch))
			for ((i = 0; i < count; i++)); do
				[[ "${done_flags[i]}" -eq 1 ]] && continue
				echo "[gate] pytest[${_buckets[i]}]: still running (${elapsed}s)"
			done
			last_heartbeat="${now}"
		fi
		sleep 2
	done
}

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

	if ((${#LIB_BUCKET_ENV[@]})); then
		for env_pair in "${LIB_BUCKET_ENV[@]}"; do
			cmd_env+=("${env_pair}")
		done
	fi

	if [[ -n "${log_file}" ]]; then
		cmd_env+=("LIB_GATE_BUCKET_NAME=${bucket}")
		cmd_env+=("LIB_PYTEST_PROGRESS_INTERVAL=1")
	fi
	if [[ "${LIB_GATE_QUIET:-false}" == "true" && "${bucket}" == "heavy" ]]; then
		cmd_env+=(
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
lib_gate_add_cleanup cleanup_tmp

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
	echo "note: pytest buckets run in parallel; progress lines appear every $(lib_pytest_progress_interval)s"
	set -m
	pids=()
	logs=()
	for bucket in "${bucket_list[@]}"; do
		log="${tmp_dir}/${bucket}.log"
		logs+=("${log}")
		(
			run_one_bucket "${bucket}" "${log}"
		) &
		bucket_pid=$!
		pids+=("${bucket_pid}")
		lib_gate_track_pid "${bucket_pid}"
	done
	set +m
	lib_pytest_wait_parallel_buckets pids logs bucket_list overall_exit
fi

exit "${overall_exit}"
