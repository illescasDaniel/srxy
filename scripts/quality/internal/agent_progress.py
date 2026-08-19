"""Sparse live progress for the quiet quality gate (agents).

Loaded via ``-p agent_progress`` when ``LIB_GATE_QUIET=true``. pytest ``-q``
hides per-test output entirely; this plugin re-adds a live ``N/total`` count so
long runs do not look dead and the gate's stall watchdog sees output.

Counting runs on the controller (non-worker) only, using nodeid sets so totals
stay deduplicated:

- total: ``pytest_collection_finish`` on serial runs; under xdist every worker
  reports the full collection, so ``pytest_xdist_node_collection_finished``
  ids are unioned (not summed).
- done/failed: ``pytest_runtest_logreport`` reports arrive on the controller
  even when workers execute the tests.
"""

from __future__ import annotations

import os
import sys


INTERVAL = int(os.environ.get("LIB_PYTEST_PROGRESS_INTERVAL", "25"))

_state = {"total": set(), "done": set(), "failed": set(), "last": 0, "worker": False}


def _count(key: str) -> int:
	return len(_state[key])


def _report() -> None:
	done = _count("done")
	total = _count("total")
	denominator = total if total else done
	ok = done - _count("failed")
	sys.stdout.write(f"[gate] {done}/{denominator} (ok={ok} fail={_count('failed')})\n")
	sys.stdout.flush()
	_state["last"] = done


def pytest_configure(config: object) -> None:
	_state["worker"] = hasattr(config, "workerinput")


def pytest_collection_finish(session: object) -> None:
	if not _state["worker"]:
		_state["total"].update(item.nodeid for item in session.items)


def pytest_xdist_node_collection_finished(node: object, ids: list[str]) -> None:
	if not _state["worker"]:
		_state["total"].update(ids)


def pytest_runtest_logreport(report: object) -> None:
	if _state["worker"]:
		return
	if report.when == "call" or (report.when == "setup" and report.failed):
		_state["done"].add(report.nodeid)
		if report.failed:
			_state["failed"].add(report.nodeid)
		if report.failed or _count("done") - _state["last"] >= INTERVAL:
			_report()


def pytest_sessionfinish(session: object, exitstatus: int) -> None:
	if not _state["worker"] and _count("done"):
		_report()
