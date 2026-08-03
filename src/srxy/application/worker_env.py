"""Shared worker/subprocess environment defaults."""

from __future__ import annotations

import os


def bootstrap_worker_env():
	os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
	os.environ.setdefault("OMP_NUM_THREADS", "1")
	os.environ.setdefault("TQDM_DISABLE", "1")
	os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
	os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
	os.environ.setdefault("JOBLIB_MULTIPROCESSING", "0")


__all__ = ["bootstrap_worker_env"]
