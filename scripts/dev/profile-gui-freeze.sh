#!/usr/bin/env bash
# Profile the live srxy GUI with py-spy while a heavy search freezes the UI.
# Usage: start the GUI, begin a heavy search, then run this in another terminal.
# Needs ptrace (often: sudo env "PATH=$PATH" bash scripts/dev/profile-gui-freeze.sh).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PYSPY="${ROOT}/.venv/bin/py-spy"
OUT="${ROOT}/.cursor/py-spy-gui-dump.txt"
SVG="${ROOT}/.cursor/py-spy-gui.svg"
SPEEDSCOPE="${ROOT}/.cursor/py-spy-gui.speedscope.json"
DURATION="${DURATION:-8}"

is_task_wrapper() {
	local cmdline="$1"
	[[ "$cmdline" == *"/bin/task "* ]] || [[ "$cmdline" == *" taskipy"* ]] || [[ "$cmdline" == *"task gui"* && "$cmdline" != *"uv run"* && "$cmdline" != *"/srxy"* ]]
}

is_gui_python() {
	local cmdline="$1"
	# Real GUI process (not the Taskipy waiter).
	[[ "$cmdline" == *"/srxy"* || "$cmdline" == *" -m srxy"* || "$cmdline" == *"adapters.inbound.gui"* ]] \
		&& [[ "$cmdline" != *"/bin/task "* ]] \
		&& [[ "$cmdline" != *"profile-gui-freeze"* ]]
}

pick_child_gui() {
	local parent="$1" child cmdline
	while read -r child; do
		[[ -z "$child" ]] && continue
		cmdline="$(ps -p "$child" -o args= 2>/dev/null || true)"
		if is_gui_python "$cmdline"; then
			echo "$child"
			return 0
		fi
		# uv/task may nest another python; recurse one level
		local grand
		grand="$(pick_child_gui "$child" || true)"
		if [[ -n "${grand:-}" ]]; then
			echo "$grand"
			return 0
		fi
	done < <(pgrep -P "$parent" 2>/dev/null || true)
	return 1
}

PID=""
CMDLINE=""
mapfile -t CANDIDATES < <(pgrep -af 'python|srxy|uv' 2>/dev/null | grep -v profile-gui-freeze | grep -v 'pgrep' || true)
for line in "${CANDIDATES[@]:-}"; do
	cand="${line%% *}"
	cmdline="${line#* }"
	if is_gui_python "$cmdline" && [[ -r "/proc/${cand}/exe" ]]; then
		PID="$cand"
		CMDLINE="$cmdline"
		break
	fi
done

# Fallback: task gui wrapper → find child srxy/uv python
if [[ -z "${PID}" ]]; then
	for line in "${CANDIDATES[@]:-}"; do
		cand="${line%% *}"
		cmdline="${line#* }"
		if [[ "$cmdline" == *"task"* && "$cmdline" == *"gui"* ]] || [[ "$cmdline" == *"/bin/task "* ]]; then
			child="$(pick_child_gui "$cand" || true)"
			if [[ -n "${child:-}" ]]; then
				PID="$child"
				CMDLINE="$(ps -p "$PID" -o args= 2>/dev/null || true)"
				echo "Resolved task wrapper PID ${cand} → GUI PID ${PID}"
				break
			fi
		fi
	done
fi

if [[ -z "${PID}" ]]; then
	echo "No live srxy GUI python process found. Start the GUI, begin a heavy search, then re-run."
	echo "Hint: pstree -p \$(pgrep -nf 'task gui') ; ps aux | grep -i srxy"
	exit 1
fi
echo "Using PID ${PID}: ${CMDLINE:-$(ps -p "$PID" -o args=)}"

run_pyspy() {
	if [[ "${EUID}" -eq 0 ]]; then
		"$@"
	else
		sudo env "PATH=${PATH}" "$@"
	fi
}

mkdir -p "${ROOT}/.cursor"
echo "Dumping stacks for PID ${PID} → ${OUT}"
run_pyspy "${PYSPY}" dump --pid "${PID}" --nonblocking >"${OUT}" 2>&1 \
	|| run_pyspy "${PYSPY}" dump --pid "${PID}" >"${OUT}" 2>&1 \
	|| true

if grep -q 'Permission Denied' "${OUT}" 2>/dev/null; then
	echo "Stack dump failed (permission). Use: sudo env \"PATH=\$PATH\" bash $0"
fi

# Use py-spy's own --duration so it flushes the flamegraph (timeout(1) often
# SIGTERMs before the SVG is written — that was why py-spy-gui.svg was missing).
rm -f "${SVG}" "${SPEEDSCOPE}"
echo "Recording ${DURATION}s of samples (rate 50) → ${SVG} (+ speedscope)"
set +e
# Prefer speedscope for interactive inspection (SVG flamegraphs often look clipped
# in image viewers). Also write SVG for a quick glance.
run_pyspy "${PYSPY}" record --pid "${PID}" --nonblocking --idle --subprocesses -r 50 -d "${DURATION}" -f speedscope -o "${SPEEDSCOPE}"
REC_RC=$?
run_pyspy "${PYSPY}" record --pid "${PID}" --nonblocking --idle --subprocesses -r 50 -d 3 -o "${SVG}" || true
set -e

if [[ -f "${SPEEDSCOPE}" || -f "${SVG}" ]]; then
	[[ -f "${SPEEDSCOPE}" ]] && echo "Wrote ${SPEEDSCOPE} — open at https://www.speedscope.app/"
	[[ -f "${SVG}" ]] && echo "Wrote ${SVG} (open in a browser; image apps often clip wide flamegraphs)"
	echo "Stack dump: ${OUT}"
else
	echo "Wrote ${OUT}"
	echo "ERROR: no profile output (py-spy exit ${REC_RC})."
	echo "  sudo env \"PATH=\$PATH\" ${PYSPY} record -p ${PID} -d 5 -f speedscope -o ${SPEEDSCOPE}"
	exit 1
fi
