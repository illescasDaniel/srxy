#!/usr/bin/env bash

# Quality gate reporting helpers. Source from scripts/quality/checks.sh after gate_init.

gate_init() {
	GATE_EMIT_GHA=false
	if [[ "${GITHUB_ACTIONS:-}" == "true" ]]; then
		GATE_EMIT_GHA=true
	fi

	GATE_TOTAL_ERRORS=0
	GATE_TOTAL_WARNINGS=0
	GATE_STEP_COUNT=0
	GATE_STEPS=()
	GATE_STEP_STATUS=()
	GATE_STEP_ERRORS=()
	GATE_STEP_WARNINGS=()
	GATE_DETAIL_LINES=()
}

gate_step_start() {
	local name="$1"
	GATE_STEP_COUNT=$((GATE_STEP_COUNT + 1))
	GATE_CURRENT_INDEX=$((GATE_STEP_COUNT - 1))
	GATE_STEPS+=("${name}")
	GATE_STEP_STATUS+=("pending")
	GATE_STEP_ERRORS+=(0)
	GATE_STEP_WARNINGS+=(0)
	echo ""
	echo "[$((GATE_CURRENT_INDEX + 1))/${GATE_PLANNED_STEPS:-?}] ${name}"
	echo "────────────────────────────────────────"
}

gate_record_step() {
	local status="$1"
	local errors="$2"
	local warnings="$3"
	GATE_STEP_STATUS[GATE_CURRENT_INDEX]="${status}"
	GATE_STEP_ERRORS[GATE_CURRENT_INDEX]="${errors}"
	GATE_STEP_WARNINGS[GATE_CURRENT_INDEX]="${warnings}"
	GATE_TOTAL_ERRORS=$((GATE_TOTAL_ERRORS + errors))
	GATE_TOTAL_WARNINGS=$((GATE_TOTAL_WARNINGS + warnings))
}

gate_add_detail() {
	GATE_DETAIL_LINES+=("$1")
}

gate_gha_error() {
	local file="${1:-}"
	local line="${2:-}"
	local col="${3:-}"
	local title="${4:-quality-gate}"
	local message="${5:-}"

	if [[ "${GATE_EMIT_GHA}" != true ]]; then
		return 0
	fi

	if [[ -n "${file}" && -n "${line}" ]]; then
		if [[ -n "${col}" ]]; then
			echo "::error file=${file},line=${line},col=${col},title=${title}::${message}"
		else
			echo "::error file=${file},line=${line},title=${title}::${message}"
		fi
	else
		echo "::error title=${title}::${message}"
	fi
}

gate_apply_emit_summary() {
	local summary_line="$1"
	local step_errors step_warnings

	step_errors="$(echo "${summary_line}" | sed -n 's/.*errors=\([0-9]*\).*/\1/p')"
	step_warnings="$(echo "${summary_line}" | sed -n 's/.*warnings=\([0-9]*\).*/\1/p')"
	step_errors="${step_errors:-0}"
	step_warnings="${step_warnings:-0}"

	if [[ "${step_errors}" -gt 0 ]]; then
		gate_record_step "FAIL" "${step_errors}" "${step_warnings}"
	elif [[ "${step_warnings}" -gt 0 ]]; then
		gate_record_step "warn" 0 "${step_warnings}"
	else
		gate_record_step "pass" 0 0
	fi
}

gate_record_pass() {
	gate_record_step "pass" 0 0
}

gate_record_fail() {
	local errors="${1:-1}"
	local warnings="${2:-0}"
	gate_record_step "FAIL" "${errors}" "${warnings}"
}

gate_print_report() {
	local i name status errors warnings status_label

	echo ""
	echo "═══════════════════════════════════════"
	echo " Quality gate report"
	echo "═══════════════════════════════════════"
	printf " %-17s %-8s %7s %9s\n" "Step" "Status" "Errors" "Warnings"
	echo " ─────────────────────────────────────────────"

	for i in "${!GATE_STEPS[@]}"; do
		name="${GATE_STEPS[i]}"
		status="${GATE_STEP_STATUS[i]}"
		errors="${GATE_STEP_ERRORS[i]}"
		warnings="${GATE_STEP_WARNINGS[i]}"
		case "${status}" in
		pass) status_label="pass" ;;
		warn) status_label="WARN" ;;
		FAIL) status_label="FAIL" ;;
		*) status_label="${status}" ;;
		esac
		printf " [%d] %-14s %-8s %7s %9s\n" "$((i + 1))" "${name}" "${status_label}" "${errors}" "${warnings}"
	done

	echo " ─────────────────────────────────────────────"
	printf " %-17s %-8s %7s %9s\n" "TOTAL" "" "${GATE_TOTAL_ERRORS}" "${GATE_TOTAL_WARNINGS}"
	echo ""

	if [[ ${#GATE_DETAIL_LINES[@]} -gt 0 ]]; then
		echo "Details:"
		for i in "${!GATE_DETAIL_LINES[@]}"; do
			echo "  ${GATE_DETAIL_LINES[i]}"
		done
		echo ""
	fi

	if [[ "${GATE_TOTAL_ERRORS}" -gt 0 ]]; then
		echo "Result: FAILED (${GATE_TOTAL_ERRORS} error(s))"
	elif [[ "${GATE_TOTAL_WARNINGS}" -gt 0 ]]; then
		echo "Result: PASSED with ${GATE_TOTAL_WARNINGS} warning(s)"
	else
		echo "Result: PASSED"
	fi
}

gate_exit() {
	gate_print_report
	if [[ "${GATE_TOTAL_ERRORS}" -gt 0 ]]; then
		exit 1
	fi
	exit 0
}
