"""Line-protocol subprocess worker that isolates Windows Property Store reads.

Some corrupt or unsupported files (e.g. a malformed JPEG) make the Windows
shell property handler raise a native SEH fault -- observed as ``0xc0000002``
(STATUS_NOT_IMPLEMENTED) -- instead of a catchable COM error. That kind of
fault takes down the whole process, so ``windows_metadata.py`` never calls
``SHGetPropertyStoreFromParsingName`` directly on the main search process on
Windows. Instead it spawns this worker and talks to it over stdio: one JSON
request per line in, one JSON response per line out. If this process dies
(native fault) the parent sees EOF on the pipe, treats it as empty metadata
for that file, and respawns a fresh worker for the next call.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _handle_request(line: str) -> str:
	from srxy.adapters.outbound.metadata.windows_metadata import _read_searchable_property_entries_direct

	try:
		request = json.loads(line)
		path = Path(request["path"])
	except (ValueError, KeyError, TypeError):
		return json.dumps({"entries": []})

	try:
		entries = _read_searchable_property_entries_direct(path)
	except Exception:
		# Any in-process failure here still fails soft; only a native SEH fault
		# (which no Python ``except`` can catch) is expected to kill this worker
		# outright, which the parent detects via EOF instead.
		entries = []
	return json.dumps({"entries": [list(entry) for entry in entries]})


def main():
	for line in sys.stdin:
		line = line.strip()
		if not line:
			continue
		response = _handle_request(line)
		sys.stdout.write(response + "\n")
		sys.stdout.flush()


if __name__ == "__main__":
	main()
