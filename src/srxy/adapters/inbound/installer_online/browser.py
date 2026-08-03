"""Open the default browser to the local installer URL."""

from __future__ import annotations

import sys
import webbrowser


def open_installer_url(url: str) -> bool:
	"""Open ``url`` in the default browser. Return False if that fails."""
	try:
		ok = webbrowser.open(url, new=2, autoraise=True)
	except Exception as exc:
		print(f"Could not open a browser automatically ({exc}).", file=sys.stderr)
		print(f"Open this URL manually:\n  {url}", file=sys.stderr)
		return False
	if not ok:
		print("Could not open a browser automatically.", file=sys.stderr)
		print(f"Open this URL manually:\n  {url}", file=sys.stderr)
		return False
	print(f"Opened installer in your browser:\n  {url}", file=sys.stderr)
	return True


__all__ = ["open_installer_url"]
