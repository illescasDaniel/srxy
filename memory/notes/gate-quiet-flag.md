---
name: gate-quiet-flag
description: Add opt-in --quiet (checks.sh) / -Quiet (checks-win.ps1) that exports LIB_GATE_QUIET=true. Pytest runs with -q --no-header -ra --tb=short -p…
type: decision
date: 2026-08-19
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** AI agents running `checks.sh` consume tens of thousands of tokens just reading the gate's stdout: pytest's `-v` addopts print one line per test (~880+ tests), and the serial heavy pass (semantic/transcribe/gui/tui/integration/ocr) reruns everything every time, streaming model/progress noise. The gate must keep streaming live output (the stall watchdog depends on it), so truncation (`tail`) was ruled out.
- **Decision:** Add opt-in `--quiet` (`checks.sh`) / `-Quiet` (`checks-win.ps1`) that exports `LIB_GATE_QUIET=true`. Pytest runs with `-q --no-header -ra --tb=short -p agent_progress` (sparse `[gate] N/total (ok=.. fail=..)` lines from the new `scripts/quality/internal/agent_progress.py` plugin; totals use nodeid sets because xdist workers each report the full collection). The heavy pass additionally gets `LIB_PYTEST_PROGRESS_INTERVAL=1` and `HF_HUB_DISABLE_PROGRESS_BARS=1`/`TRANSFORMERS_VERBOSITY=error`/`TOKENIZERS_PARALLELISM=false`/`TQDM_DISABLE=1`. On the parallel-verify path, passing light-step logs are no longer replayed (`gate_finish_step` loads the status first and cats the log only on failure or non-quiet). Taskipy task naming was later revised — see the "Taskipy gate tasks: non-quiet by default, dedicated `*-quiet` variants" entry above. `-p no:cacheprovider` was dropped because disabling the cacheprovider also removes pytest's `--ff` (fail-first) option, which the local gate passes.
- **Rationale:** Keeps the human-facing verbose default while slashing agent token cost; failures still show full short tracebacks + `-ra` summary; progress lines keep the stall watchdog satisfied during slow heavy tests. Verified with `uv run task checks` and `uv run task checks-fix` (both PASSED, 122 heavy tests).
