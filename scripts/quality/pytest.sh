#!/usr/bin/env bash

set -euo pipefail

quality_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=internal/lib.sh
source "${quality_dir}/internal/lib.sh"
# shellcheck source=internal/run_with_watch.sh
source "${quality_dir}/internal/run_with_watch.sh"

lib_require_venv
lib_pytest_args

if [[ ${#LIB_PYTEST_ARGS[@]} -eq 0 ]]; then
	echo "No pytest test directory found (expected tests/ or test/)" >&2
	exit 1
fi

# Defaults: CI unit suite ~15s; allow headroom. Stall catches silent xdist freeze.
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
# Optional overlay for plugins when the project venv cannot be mutated (agent sandbox).
if [[ -n "${SRXY_PYTEST_PYTHONPATH:-}" ]]; then
	export PYTHONPATH="${SRXY_PYTEST_PYTHONPATH}${PYTHONPATH:+:${PYTHONPATH}}"
fi

# Quiet mode (LIB_GATE_QUIET=true): collapse pytest -v output to sparse
# N/total progress lines (agent_progress plugin) plus failure detail.
quiet_args=()
if [[ "${LIB_GATE_QUIET:-false}" == "true" ]]; then
	quiet_args=(-q --no-header -ra --tb=short -p agent_progress)
	export PYTHONPATH="${quality_dir}/internal${PYTHONPATH:+:${PYTHONPATH}}"
fi

workers_label="$(_lib_pytest_worker_count)"
echo "pytest: safe parallel pass (workers=${workers_label} wall=${LIB_PYTEST_WALL_SECONDS}s stall=${LIB_PYTEST_STALL_SECONDS}s)"
echo "pytest: args: ${LIB_PYTEST_ARGS[*]} ${LIB_PYTEST_COV[*]:-}"

cd "${LIB_REPO_ROOT}" || exit 1
pytest_bin=("${LIB_REPO_ROOT}/.venv/bin/python" -m pytest)

set +e
lib_run_with_watch "${LIB_PYTEST_WALL_SECONDS}" "${LIB_PYTEST_STALL_SECONDS}" -- \
	"${pytest_bin[@]}" "${LIB_PYTEST_ARGS[@]}" ${LIB_PYTEST_COV[@]+"${LIB_PYTEST_COV[@]}"} ${quiet_args[@]+"${quiet_args[@]}"}
pytest_exit=$?
set -e

if [[ "${pytest_exit}" -ne 0 ]]; then
	exit "${pytest_exit}"
fi

lib_pytest_heavy_args
if [[ ${#LIB_PYTEST_HEAVY_ARGS[@]} -gt 0 ]]; then
	echo ""
	echo "Serial heavy pass (semantic/transcribe/gui/tui/integration/ocr, QT_QPA_PLATFORM=offscreen, -n 0)"
	echo "pytest: starting (workers=0 wall=${LIB_PYTEST_WALL_SECONDS}s stall=${LIB_PYTEST_STALL_SECONDS}s)"
	echo "pytest: args: ${LIB_PYTEST_HEAVY_ARGS[*]} ${LIB_PYTEST_HEAVY_COV[*]:-}"
	heavy_env=(QT_QPA_PLATFORM=offscreen)
	if [[ "${LIB_GATE_QUIET:-false}" == "true" ]]; then
		heavy_env+=(
			LIB_PYTEST_PROGRESS_INTERVAL=1
			HF_HUB_DISABLE_PROGRESS_BARS=1
			TRANSFORMERS_VERBOSITY=error
			TOKENIZERS_PARALLELISM=false
			TQDM_DISABLE=1
		)
	fi
	set +e
	lib_run_with_watch "${LIB_PYTEST_WALL_SECONDS}" "${LIB_PYTEST_STALL_SECONDS}" -- \
		env ${heavy_env[@]+"${heavy_env[@]}"} "${pytest_bin[@]}" "${LIB_PYTEST_HEAVY_ARGS[@]}" ${LIB_PYTEST_HEAVY_COV[@]+"${LIB_PYTEST_HEAVY_COV[@]}"} ${quiet_args[@]+"${quiet_args[@]}"}
	pytest_exit=$?
	set -e
fi

exit "${pytest_exit}"
