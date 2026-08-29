#!/usr/bin/env bash

# Shared helpers for quality gate scripts (bucketed pytest + tool runners).

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

# Prefer direct venv executables (skip uv env revalidation). Fall back to `uv run`.
lib_venv_bin() {
	local name="$1"
	if [[ -x "${LIB_REPO_ROOT}/.venv/bin/${name}" ]]; then
		echo "${LIB_REPO_ROOT}/.venv/bin/${name}"
		return 0
	fi
	return 1
}

lib_uv_run() {
	cd "${LIB_REPO_ROOT}" || return
	local bin
	if bin="$(lib_venv_bin "$1")" && [[ -n "${bin}" ]]; then
		shift
		"${bin}" "$@"
		return $?
	fi
	UV_NO_SYNC=1 uv run -- "$@"
}

lib_python() {
	if [[ -x "${LIB_REPO_ROOT}/.venv/bin/python" ]]; then
		echo "${LIB_REPO_ROOT}/.venv/bin/python"
	else
		echo "uv"
	fi
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
	# Targeted enumeration — do not recurse .venv / node_modules / dist.
	{
		find "${LIB_REPO_ROOT}/scripts" -name "*.sh" 2>/dev/null
		find "${LIB_REPO_ROOT}/packaging" -name "*.sh" 2>/dev/null
		find "${LIB_REPO_ROOT}" -maxdepth 1 -name "*.sh" 2>/dev/null
	} | sort -u
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

# ---------------------------------------------------------------------------
# Pytest buckets
# ---------------------------------------------------------------------------

# Ordered longest-job-first for scheduling.
LIB_BUCKET_ORDER=(heavy gui tui core)

_lib_nproc() {
	local n
	n="$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 2)"
	if [[ "${n}" -lt 1 ]]; then
		n=1
	fi
	echo "${n}"
}

_lib_pytest_worker_count() {
	local n reserved cap
	if [[ -n "${LIB_PYTEST_WORKERS:-}" ]]; then
		echo "${LIB_PYTEST_WORKERS}"
		return
	fi
	n="$(_lib_nproc)"
	reserved="${LIB_GATE_ACTIVE_BUCKETS:-1}"
	# Leave a core for each concurrent non-core bucket; raise former cap of 4.
	cap=$((n - reserved + 1))
	if [[ "${cap}" -lt 2 ]]; then
		cap=2
	fi
	if [[ "${cap}" -gt 8 ]]; then
		cap=8
	fi
	if [[ "${n}" -lt "${cap}" ]]; then
		cap="${n}"
	fi
	echo "${cap}"
}

# Parse LIB_GATE_SCOPE (auto|all|comma-list|shorthand already expanded by caller).
# Sets LIB_SELECTED_BUCKETS (space-separated) and LIB_SCOPE_REASON.
lib_resolve_buckets() {
	local scope="${LIB_GATE_SCOPE:-auto}"
	local bucket
	local -a selected=()
	local reason=""

	case "${scope}" in
	all | full)
		selected=("${LIB_BUCKET_ORDER[@]}")
		# CI day-to-day skips heavy (real models) unless --full / --all forced.
		if [[ "${CI:-}" == "true" && "${LIB_PYTEST_FULL:-}" != "true" && "${scope}" != "all" ]]; then
			selected=(gui tui core)
			reason="CI default (core+gui+tui)"
		else
			reason="explicit all"
		fi
		;;
	auto)
		lib_auto_scope_buckets
		return
		;;
	*)
		IFS=',' read -r -a selected <<<"${scope}"
		reason="explicit --scope=${scope}"
		;;
	esac

	# Normalize + de-dupe while preserving LIB_BUCKET_ORDER.
	LIB_SELECTED_BUCKETS=()
	for bucket in "${LIB_BUCKET_ORDER[@]}"; do
		local s
		for s in "${selected[@]}"; do
			s="$(echo "${s}" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
			# cli is an alias that always implies core (cli tests live under tests/cli).
			if [[ "${s}" == "cli" ]]; then
				s="core"
			fi
			if [[ "${s}" == "${bucket}" ]]; then
				LIB_SELECTED_BUCKETS+=("${bucket}")
				break
			fi
		done
	done
	if [[ ${#LIB_SELECTED_BUCKETS[@]} -eq 0 ]]; then
		LIB_SELECTED_BUCKETS=(core)
		reason="${reason}; fell back to core (empty selection)"
	fi
	LIB_SCOPE_REASON="${reason}"
}

lib_auto_scope_buckets() {
	local -a paths=()
	local want_core=1 want_gui=0 want_tui=0 want_heavy=0
	local line path merge_base
	local ambiguous=false

	if ! command -v git >/dev/null 2>&1 || ! git -C "${LIB_REPO_ROOT}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
		LIB_SELECTED_BUCKETS=("${LIB_BUCKET_ORDER[@]}")
		LIB_SCOPE_REASON="auto → all (no git)"
		return
	fi

	merge_base="$(git -C "${LIB_REPO_ROOT}" merge-base HEAD origin/main 2>/dev/null || git -C "${LIB_REPO_ROOT}" merge-base HEAD main 2>/dev/null || true)"
	if [[ -n "${merge_base}" ]]; then
		while IFS= read -r line; do
			[[ -n "${line}" ]] && paths+=("${line}")
		done < <(git -C "${LIB_REPO_ROOT}" diff --name-only "${merge_base}...HEAD" 2>/dev/null)
	fi
	while IFS= read -r line; do
		# porcelain: XY PATH or rename "XY PATH -> PATH"
		path="${line:3}"
		path="${path%% -> *}"
		path="${path#"${path%%[![:space:]]*}"}"
		[[ -n "${path}" ]] && paths+=("${path}")
	done < <(git -C "${LIB_REPO_ROOT}" status --porcelain 2>/dev/null)

	if [[ ${#paths[@]} -eq 0 ]]; then
		LIB_SELECTED_BUCKETS=(core)
		LIB_SCOPE_REASON="auto → core (clean tree)"
		return
	fi

	for path in "${paths[@]}"; do
		case "${path}" in
		src/srxy/adapters/inbound/gui/* | src/srxy/adapters/inbound/shared/qml/* | src/srxy/adapters/inbound/installer/* | tests/gui/*)
			want_gui=1
			;;
		src/srxy/adapters/inbound/tui/* | tests/tui/*)
			want_tui=1
			;;
		src/srxy/adapters/inbound/cli/* | tests/cli/*)
			want_core=1
			;;
		src/srxy/adapters/outbound/semantic/* | src/srxy/adapters/outbound/transcribe/* | src/srxy/adapters/outbound/ocr/* | src/srxy/adapters/outbound/models/* | src/srxy/application/matching/semantic.py | tests/fixtures/* | tests/integration/*)
			want_heavy=1
			;;
		pyproject.toml | tests/conftest.py | tests/helpers.py | tests/isolation.py | scripts/quality/* | .github/*)
			ambiguous=true
			;;
		src/srxy/* | tests/unit/* | packaging/* | scripts/* | assets/*)
			want_core=1
			;;
		*)
			# Unknown path — stay conservative.
			ambiguous=true
			;;
		esac
	done

	if [[ "${ambiguous}" == true ]]; then
		LIB_SELECTED_BUCKETS=("${LIB_BUCKET_ORDER[@]}")
		LIB_SCOPE_REASON="auto → all (ambiguous paths)"
		return
	fi

	# CI day-to-day never auto-selects heavy.
	if [[ "${CI:-}" == "true" && "${LIB_PYTEST_FULL:-}" != "true" ]]; then
		want_heavy=0
	fi

	LIB_SELECTED_BUCKETS=()
	# Longest-job-first order.
	if [[ "${want_heavy}" -eq 1 ]]; then
		LIB_SELECTED_BUCKETS+=(heavy)
	fi
	if [[ "${want_gui}" -eq 1 ]]; then
		LIB_SELECTED_BUCKETS+=(gui)
	fi
	if [[ "${want_tui}" -eq 1 ]]; then
		LIB_SELECTED_BUCKETS+=(tui)
	fi
	if [[ "${want_core}" -eq 1 ]]; then
		LIB_SELECTED_BUCKETS+=(core)
	fi
	LIB_SCOPE_REASON="auto → ${LIB_SELECTED_BUCKETS[*]}"
}

# Build pytest argv for one bucket into LIB_BUCKET_ARGS (array).
# Also sets LIB_BUCKET_ENV as "KEY=VAL KEY=VAL" for the caller to export.
lib_bucket_args() {
	local bucket="$1"
	LIB_BUCKET_ARGS=()
	LIB_BUCKET_ENV=()
	LIB_BUCKET_TESTMON_FILE=""

	local -a paths=()
	local workers=0
	local enable_qt=false
	local cov_append=false

	case "${bucket}" in
	core)
		paths=(tests/unit tests/cli)
		workers="$(_lib_pytest_worker_count)"
		LIB_BUCKET_TESTMON_FILE=".testmondata-core"
		;;
	gui)
		paths=(tests/gui)
		workers=0
		enable_qt=true
		LIB_BUCKET_ENV+=(QT_QPA_PLATFORM=offscreen)
		LIB_BUCKET_TESTMON_FILE=".testmondata-gui"
		;;
	tui)
		paths=(tests/tui)
		workers=0
		LIB_BUCKET_TESTMON_FILE=".testmondata-tui"
		;;
	heavy)
		paths=(tests/integration)
		workers=0
		LIB_BUCKET_ENV+=(
			QT_QPA_PLATFORM=offscreen
			OMP_NUM_THREADS=1
			MKL_NUM_THREADS=1
			TOKENIZERS_PARALLELISM=false
		)
		if [[ "${LIB_PYTEST_FULL:-}" != "true" ]]; then
			# Prefer offline HF when models are already cached (day-to-day).
			LIB_BUCKET_ENV+=(HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1)
		fi
		LIB_BUCKET_TESTMON_FILE=".testmondata-heavy"
		;;
	*)
		echo "unknown bucket: ${bucket}" >&2
		return 1
		;;
	esac

	local p
	for p in "${paths[@]}"; do
		if [[ -d "${LIB_REPO_ROOT}/${p}" ]]; then
			LIB_BUCKET_ARGS+=("${p}")
		fi
	done
	if [[ ${#LIB_BUCKET_ARGS[@]} -eq 0 ]]; then
		return 0
	fi

	# Marker filters within a path bucket.
	case "${bucket}" in
	core)
		# Paths already isolate Qt/Textual/real backends; no -m filter needed.
		# Keep unit-marked integration-style tests (e.g. installer engine) in core.
		;;
	heavy)
		if [[ "${LIB_PYTEST_FULL:-}" == "true" ]]; then
			: # run everything under tests/integration
		else
			LIB_BUCKET_ARGS+=(-m "not integration_full and not transcribe_device_matrix")
		fi
		if [[ "${LIB_PYTEST_FULL_CPU:-}" == "true" ]]; then
			LIB_BUCKET_ARGS+=(--integration-test-cpu)
		fi
		;;
	esac

	if [[ "${workers}" -gt 0 ]]; then
		LIB_BUCKET_ARGS+=(-n "${workers}" --dist=loadgroup --max-worker-restart=0)
	fi
	# Serial buckets omit -n; keep xdist loaded so agent_progress xdist hooks validate.

	if [[ "${enable_qt}" != true ]]; then
		LIB_BUCKET_ARGS+=(-p no:pytest-qt)
	fi

	# Coverage only on --full.
	if [[ "${LIB_PYTEST_FULL:-}" == "true" && -d "${LIB_REPO_ROOT}/src" ]]; then
		if [[ "${bucket}" == "core" ]]; then
			LIB_BUCKET_ARGS+=(--cov=src --cov-report=term-missing:skip-covered -ra --tb=short)
		else
			LIB_BUCKET_ARGS+=(--cov=src --cov-append --cov-report=term-missing:skip-covered -ra --tb=short)
		fi
	else
		LIB_BUCKET_ARGS+=(-p no:pytest_cov)
	fi

	# Per-bucket testmon (day-to-day only).
	if [[ "${CI:-}" != "true" && "${LIB_PYTEST_FULL:-}" != "true" && -n "${LIB_BUCKET_TESTMON_FILE}" ]]; then
		LIB_BUCKET_ENV+=("TESTMON_DATAFILE=${LIB_BUCKET_TESTMON_FILE}")
		LIB_BUCKET_ARGS+=(--testmon-forceselect --ff)
	fi

	if [[ "${LIB_GATE_TIMINGS:-false}" == "true" ]]; then
		LIB_BUCKET_ARGS+=(--durations=25)
	fi
}

# Content-hash step cache under .gate-cache/
lib_gate_cache_dir() {
	echo "${LIB_REPO_ROOT}/.gate-cache"
}

lib_hash_file() {
	local f="$1"
	if command -v sha256sum >/dev/null 2>&1; then
		sha256sum "${f}" | awk '{print $1}'
	elif command -v shasum >/dev/null 2>&1; then
		shasum -a 256 "${f}" | awk '{print $1}'
	else
		# Fallback: python
		"$(lib_python)" -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "${f}"
	fi
}

# Returns 0 if the cached step can be skipped.
lib_cache_hit() {
	local name="$1"
	local hash="$2"
	local max_age_days="${3:-7}"
	local dir marker
	if [[ "${LIB_GATE_NO_CACHE:-false}" == "true" || "${LIB_PYTEST_FULL:-}" == "true" || "${CI:-}" == "true" ]]; then
		return 1
	fi
	dir="$(lib_gate_cache_dir)"
	marker="${dir}/${name}.ok"
	[[ -f "${marker}" ]] || return 1
	[[ "$(cat "${marker}")" == "${hash}" ]] || return 1
	# Age check (GNU/BSD find -mtime).
	if find "${marker}" -mtime "+${max_age_days}" 2>/dev/null | grep -q .; then
		return 1
	fi
	return 0
}

lib_cache_store() {
	local name="$1"
	local hash="$2"
	local dir
	dir="$(lib_gate_cache_dir)"
	mkdir -p "${dir}"
	printf '%s\n' "${hash}" >"${dir}/${name}.ok"
}

# Back-compat wrappers used by older callers / docs.
lib_pytest_args() {
	lib_resolve_buckets
	lib_bucket_args core
	# shellcheck disable=SC2034
	LIB_PYTEST_ARGS=("${LIB_BUCKET_ARGS[@]}")
	# shellcheck disable=SC2034
	LIB_PYTEST_COV=()
}

lib_pytest_heavy_args() {
	# shellcheck disable=SC2034
	LIB_PYTEST_HEAVY_ARGS=()
	# shellcheck disable=SC2034
	LIB_PYTEST_HEAVY_COV=()
}
