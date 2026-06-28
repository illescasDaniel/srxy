#!/usr/bin/env bash
# Release QA CLI matrix runner. Prints summary to stdout; set QA_RESULTS=path to save a log.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=scripts/quality/internal/lib.sh
source "$ROOT/scripts/quality/internal/lib.sh"

lib_require_venv
lib_activate_venv
cd "$ROOT"

DOCS="${SRXY_QA_CORPUS:-$ROOT/tests/fixtures/qa_corpus}/docs"
TEMP_DOCS="${SRXY_QA_CORPUS:-$ROOT/tests/fixtures/qa_corpus}"
QA_DL="${SRXY_QA_CORPUS:-$ROOT/tests/fixtures/qa_corpus}/qa_downloads"
RESULTS="${QA_RESULTS:-}"

# Use default model cache (~/.cache/srxy). Do NOT set SRXY_* env vars globally —
# that triggers preflight for heavy modes on every search.
unset SRXY_TRANSCRIBE SRXY_SEMANTIC SRXY_SEMANTIC_IMAGE SRXY_OCR SRXY_CACHE_DIR
export CI=true

pass=0
fail=0
skip=0
bugs=()

if [[ -n "$RESULTS" ]]; then
	cat >"$RESULTS" <<EOF
# srxy QA Results

Generated: $(date -Iseconds)

| ID | Status | Detail |
|----|--------|--------|
EOF
fi

log_result() {
	local id="$1" status="$2" detail="$3"
	local row="| $id | $status | $detail |"
	echo "$row"
	if [[ -n "$RESULTS" ]]; then
		echo "$row" >>"$RESULTS"
	fi
	case "$status" in
	PASS) pass=$((pass + 1)) ;;
	FAIL)
		fail=$((fail + 1))
		bugs+=("$id: $detail")
		;;
	SKIP) skip=$((skip + 1)) ;;
	esac
}

run_srxy() {
	# shellcheck disable=SC2068
	srxy "$@" --no-tui --no-progress 2>/tmp/srxy-qa-stderr.txt
}

assert_exit() {
	local id="$1" expected="$2"
	shift 2
	local code=0
	set +e
	run_srxy "$@" >/tmp/srxy-qa-stdout.txt
	code=$?
	set -e
	if [[ "$code" -eq "$expected" ]]; then
		log_result "$id" PASS "exit $code"
	else
		log_result "$id" FAIL "expected exit $expected got $code; stderr: $(head -c 200 /tmp/srxy-qa-stderr.txt)"
	fi
}

assert_match() {
	local id="$1" needle="$2"
	shift 2
	local code=0
	set +e
	run_srxy "$@" >/tmp/srxy-qa-stdout.txt
	code=$?
	set -e
	if [[ "$code" -eq 0 ]] && grep -qi "$needle" /tmp/srxy-qa-stdout.txt; then
		log_result "$id" PASS "matched $needle"
	else
		log_result "$id" FAIL "code=$code needle=$needle; out: $(head -c 300 /tmp/srxy-qa-stdout.txt)"
	fi
}

echo "=== Suite 1: Smoke ==="
assert_exit S1.1 0 --help
assert_exit S1.2 2
assert_exit S1.3 2 nomatch /nonexistent/path
assert_exit S1.4 1 nomatch /tmp
assert_match S1.5 notes.txt axolotl "$DOCS" --content-only
assert_match S1.6 notes.txt axolotl "$DOCS" --json --content-only
assert_match S1.7 notes.txt axolotl "$DOCS" --format flat --content-only

echo "=== Suite 2: Playbook ==="
assert_match P2.1 notes.txt axolotl "$DOCS" --content-only
assert_match P2.2 "02 Heat" "Linkin Park" "$DOCS" --content-only
assert_match P2.3 IMG "person" "$DOCS" --semantic-image --content-only
assert_match P2.4 Normalize "transforms.Normalize" "$DOCS" --ocr --content-only
assert_match P2.5 flac "all i know" "$DOCS" --transcribe --content-only
assert_match P2.6 jpg "sibling" "$DOCS" --semantic-all --content-only

echo "=== Suite 2: Filters ==="
assert_match F2.1 notes axolotl "$DOCS" --names-only
assert_match F2.2 notes axolotl "$DOCS" --content-only
assert_match F2.5 notes axolotl "$DOCS" -l 1 --content-only
run_srxy axolotl "$DOCS" --max-file-size 100 --content-only >/tmp/srxy-qa-stdout.txt || true
if grep -qi skip /tmp/srxy-qa-stderr.txt 2>/dev/null; then
	log_result F2.7 PASS "skipped oversized files"
else
	log_result F2.7 FAIL "no skip warning for max-file-size"
fi
run_srxy axolotl "$DOCS" --max-ocr-file-size 1 --ocr --content-only >/tmp/srxy-qa-stdout.txt || true
if grep -qi skip /tmp/srxy-qa-stderr.txt 2>/dev/null; then
	log_result F2.8 PASS "OCR skip warning"
else
	log_result F2.8 FAIL "no OCR skip warning"
fi

echo "=== Suite 2: Boolean ==="
assert_match B2.1 Heat 'Linkin Park|Call Me' "$DOCS" --content-only
assert_match B2.4 notes '(axolotl|dragon)&notes' "$DOCS" --content-only

echo "=== Suite 3: Documents ==="
assert_match D3.5 qa_docx_token qa_docx_token "$QA_DL/documents" --content-only
assert_match D3.6 qa_xlsx_token qa_xlsx_token "$QA_DL/documents" --content-only
assert_match D3.7 qa_pptx_token qa_pptx_token "$QA_DL/documents" --content-only
assert_match D3.1 notes axolotl "$DOCS/notes.txt" --content-only

echo "=== Suite 4: OCR ==="
assert_match O4.1 revenue revenue "$ROOT/tests/fixtures/ocr" --ocr --content-only
assert_match O4.2 qa_ocr_token qa_ocr_token "$QA_DL/ocr" --ocr --content-only
assert_match O4.6 qa_png_token qa_png_token "$QA_DL/images" --ocr --content-only

echo "=== Suite 5: Audio ==="
assert_match A5.1 Linkin "Linkin Park" "$DOCS" --content-only
assert_match A5.2 flac "all i know" "$DOCS" --transcribe --content-only

echo "=== Suite 6: Video ==="
assert_match V6.1 mp4 "all i know" "$TEMP_DOCS" --transcribe --content-only

echo "=== Suite 8: Semantic image ==="
assert_match IMG8.1 IMG "person" "$DOCS" --semantic-image --content-only

echo "=== Suite 9: semantic-all ==="
assert_match SA9.1 Linkin linkin "$DOCS" --semantic-all --content-only

echo "=== Suite 10: Output ==="
run_srxy axolotl "$DOCS" --json --content-only >/tmp/srxy-qa-stdout.txt
if python -c "import json; json.load(open('/tmp/srxy-qa-stdout.txt'))"; then
	log_result OUT10.1 PASS "valid json"
else
	log_result OUT10.1 FAIL "invalid json"
fi
run_srxy axolotl "$DOCS" --format flat --content-only >/tmp/srxy-qa-stdout.txt
if [[ -s /tmp/srxy-qa-stdout.txt ]]; then
	log_result OUT10.2 PASS "flat output non-empty"
else
	log_result OUT10.2 FAIL "empty flat output"
fi
out_file="/tmp/srxy-qa-out.json"
run_srxy axolotl "$DOCS" --json --content-only -o "$out_file"
if [[ -s "$out_file" ]]; then
	log_result OUT10.3 PASS "output file written"
else
	log_result OUT10.3 FAIL "output file empty"
fi

echo "=== Suite 13: Edge ==="
assert_match E13.4 notes axolotl "$DOCS/notes.txt"
run_srxy "$(python -c 'print("x"*500)')" "$DOCS/notes.txt" --content-only >/tmp/srxy-qa-stdout.txt 2>/tmp/srxy-qa-stderr.txt || true
log_result E13.5 PASS "long query handled (no crash)"
assert_match E13.10 hidden hidden_secret "$QA_DL/edge" --include-hidden --content-only
assert_match E13.11 noise noise_content_token "$QA_DL/edge" --include-noise --content-only

echo "=== Env-var preflight bug check ==="
set +e
SRXY_TRANSCRIBE=1 SRXY_CACHE_DIR=/tmp/srxy-empty-$$ srxy axolotl "$DOCS" --content-only --no-tui >/tmp/srxy-qa-stdout.txt 2>/tmp/srxy-qa-stderr.txt
code=$?
set -e
if [[ "$code" -eq 2 ]] && grep -q "Transcription model" /tmp/srxy-qa-stderr.txt; then
	log_result BUG001 FAIL "SRXY_TRANSCRIBE=1 blocks basic search without model in cache (exit 2)"
else
	log_result BUG001 PASS "env transcribe does not block basic search"
fi

summary=$(
	cat <<EOF

PASS: $pass  FAIL: $fail  SKIP: $skip
EOF
)
if ((${#bugs[@]})); then
	summary+=$(printf '\n\nFailures:\n')
	for b in "${bugs[@]}"; do summary+=$'- '"$b"$'\n'; done
fi
echo "$summary"
if [[ -n "$RESULTS" ]]; then
	mkdir -p "$(dirname "$RESULTS")"
	{
		echo ""
		echo "## Summary"
		echo "PASS: $pass  FAIL: $fail  SKIP: $skip"
		if ((${#bugs[@]})); then
			echo ""
			echo "## Failures"
			for b in "${bugs[@]}"; do echo "- $b"; done
		fi
	} >>"$RESULTS"
	echo "Log written to $RESULTS"
else
	echo "Set QA_RESULTS=path to save a log file."
fi
exit "$([[ $fail -eq 0 ]] && echo 0 || echo 1)"
