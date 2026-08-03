#!/usr/bin/env bash

# Run a command with live stdout/stderr, a wall-clock limit, and a no-output stall limit.
# Usage: lib_run_with_watch <wall_seconds> <stall_seconds> -- <command> [args...]
# Exit 124 on wall or stall timeout (after killing the process group).

lib_run_with_watch() {
	local wall_seconds="$1"
	local stall_seconds="$2"
	shift 2
	if [[ "${1:-}" != "--" ]]; then
		echo "lib_run_with_watch: expected -- before command" >&2
		return 2
	fi
	shift

	if [[ "$#" -lt 1 ]]; then
		echo "lib_run_with_watch: missing command" >&2
		return 2
	fi

	local fifo log
	fifo="$(mktemp -u "${TMPDIR:-/tmp}/srxy-watch.XXXXXX.fifo")"
	log="$(mktemp "${TMPDIR:-/tmp}/srxy-watch.XXXXXX.log")"
	mkfifo "${fifo}"

	export PYTHONUNBUFFERED=1

	# Own process group so xdist workers die with the leader.
	setsid stdbuf -oL -eL "$@" >"${fifo}" 2>&1 &
	local cmd_pid=$!

	local reader_pid
	(
		while IFS= read -r line || [[ -n "${line}" ]]; do
			printf '%s\n' "${line}"
			printf '%s\n' "${line}" >>"${log}"
			# Touch mtime for stall detection without parsing size races.
			touch "${log}.beat"
		done <"${fifo}"
	) &
	reader_pid=$!

	touch "${log}.beat"
	local start_epoch beat_epoch now
	start_epoch="$(date +%s)"

	local exit_code=0
	while kill -0 "${cmd_pid}" 2>/dev/null; do
		now="$(date +%s)"
		if ((now - start_epoch >= wall_seconds)); then
			echo "error: command exceeded wall clock (${wall_seconds}s): $*" >&2
			echo "--- last output ---" >&2
			tail -n 40 "${log}" >&2 || true
			kill -TERM -"${cmd_pid}" 2>/dev/null || kill -TERM "${cmd_pid}" 2>/dev/null || true
			sleep 2
			kill -KILL -"${cmd_pid}" 2>/dev/null || kill -KILL "${cmd_pid}" 2>/dev/null || true
			exit_code=124
			break
		fi
		beat_epoch="$(stat -c %Y "${log}.beat" 2>/dev/null || stat -f %m "${log}.beat" 2>/dev/null || echo "${now}")"
		if ((now - beat_epoch >= stall_seconds)); then
			echo "error: no output for ${stall_seconds}s (stall): $*" >&2
			echo "--- process tree ---" >&2
			if command -v pstree >/dev/null 2>&1; then
				pstree -p "${cmd_pid}" >&2 || true
			else
				ps -ef | grep -E "[p]ytest|[x]dist" >&2 || true
			fi
			echo "--- last output ---" >&2
			tail -n 40 "${log}" >&2 || true
			echo "hint: stop leftover pytest/checks.sh for this repo; retry. Optional: CUDA_VISIBLE_DEVICES=\"\"" >&2
			kill -TERM -"${cmd_pid}" 2>/dev/null || kill -TERM "${cmd_pid}" 2>/dev/null || true
			sleep 2
			kill -KILL -"${cmd_pid}" 2>/dev/null || kill -KILL "${cmd_pid}" 2>/dev/null || true
			exit_code=124
			break
		fi
		sleep 1
	done

	if [[ "${exit_code}" -eq 0 ]]; then
		wait "${cmd_pid}"
		exit_code=$?
	else
		wait "${cmd_pid}" 2>/dev/null || true
	fi

	# Unblock reader if still waiting on fifo.
	kill "${reader_pid}" 2>/dev/null || true
	wait "${reader_pid}" 2>/dev/null || true
	rm -f "${fifo}" "${log}" "${log}.beat"
	return "${exit_code}"
}
