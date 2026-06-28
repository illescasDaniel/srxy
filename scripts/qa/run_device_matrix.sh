#!/usr/bin/env bash
# Device matrix for transcription: CUDA vs CPU parity check.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=scripts/quality/internal/lib.sh
source "$ROOT/scripts/quality/internal/lib.sh"
lib_require_venv
lib_activate_venv

DOCS="${SRXY_QA_CORPUS:-$ROOT/tests/fixtures/qa_corpus}/docs"
TEMP_DOCS="${SRXY_QA_CORPUS:-$ROOT/tests/fixtures/qa_corpus}"
RESULTS="${QA_DEVICE_RESULTS:-}"
QUERY="all i know"

cuda_available() {
	python -c "import torch; raise SystemExit(0 if torch.cuda.is_available() else 1)" 2>/dev/null
}

qa_test_cpu_requested() {
	case "${SRXY_QA_TEST_CPU:-}" in
	1 | true | yes | on | TRUE | YES | ON) return 0 ;;
	esac
	return 1
}

header="# Transcription Device Matrix

Generated: $(date -Iseconds)
Query: $QUERY

| ID | Device | Target | Exit | Top match | Time(s) |
|----|--------|--------|------|-----------|---------|"
echo "$header"
if [[ -n "$RESULTS" ]]; then
	mkdir -p "$(dirname "$RESULTS")"
	printf '%s\n' "$header" >"$RESULTS"
fi

run_device() {
	local id="$1" device="$2" path="$3" label="$4"
	local start end elapsed out code
	start=$(date +%s.%N)
	set +e
	out=$(SRXY_TRANSCRIBE_DEVICE="$device" srxy "$QUERY" "$path" --transcribe --content-only --no-tui --no-progress 2>/tmp/srxy-dev-stderr.txt)
	code=$?
	set -e
	end=$(date +%s.%N)
	elapsed=$(python -c "print(f'{$end - $start:.1f}')")
	top=$(echo "$out" | grep -m1 '──' | sed 's/── //g; s/ ──//g' || echo "none")
	local row="| $id | $device | $label | $code | $top | $elapsed |"
	echo "$row"
	if [[ -n "$RESULTS" ]]; then
		echo "$row" >>"$RESULTS"
	fi
	echo "$id $device $label: exit=$code top=$top time=${elapsed}s"
}

if cuda_available; then
	run_device A5.2-cuda cuda "$DOCS" "audio flacs"
	run_device V6.1-cuda cuda "$TEMP_DOCS" "video+audio tree"
	if qa_test_cpu_requested; then
		run_device A5.2-cpu cpu "$DOCS" "audio flacs"
		run_device V6.1-cpu cpu "$TEMP_DOCS" "video+audio tree"
	else
		echo "CUDA available — skipping forced CPU runs (set SRXY_QA_TEST_CPU=1 to include them)"
	fi
else
	run_device A5.2-cpu cpu "$DOCS" "audio flacs"
	run_device V6.1-cpu cpu "$TEMP_DOCS" "video+audio tree"
fi

if [[ -n "$RESULTS" ]]; then
	echo "Log written to $RESULTS"
else
	echo "Set QA_DEVICE_RESULTS=path to save a log file."
fi
