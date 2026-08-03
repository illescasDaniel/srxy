"""Localhost HTTP server for the one-click online installer UI."""

from __future__ import annotations

import json
import mimetypes
import secrets
import sys
import threading
import time
import traceback
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from srxy.adapters.inbound.installer.install import install_srxy
from srxy.adapters.inbound.installer.privacy import privacy_disclaimer_text
from srxy.adapters.inbound.installer_online.browser import open_installer_url
from srxy.adapters.inbound.installer_online.options import build_online_install_options
from srxy.application.install_paths import default_install_prefix
from srxy.i18n import resolve_language, set_language, tr


TOKEN_HEADER = "X-Srxy-Installer-Token"  # noqa: S105
STATIC_DIR = Path(__file__).resolve().parent / "static"

# Browser gone → stop process (Dolphin double-click has no terminal).
DEFAULT_CLIENT_IDLE_SECONDS = 3.0
# Allow time for the default browser to open the installer URL.
DEFAULT_CLIENT_GRACE_SECONDS = 20.0


class InstallSession:
	"""Thread-safe install progress shared with HTTP handlers."""

	def __init__(self, *, token: str):
		self.token = token
		self._lock = threading.Lock()
		self.status = "idle"
		self.message = ""
		self.overall = 0.0
		self.task = 0.0
		self.error = ""
		self._install_started = False
		self.stop_event = threading.Event()
		self.started_at = time.monotonic()
		self.last_client_seen: float | None = None

	def touch_client(self):
		with self._lock:
			self.last_client_seen = time.monotonic()

	def client_activity(self) -> tuple[float, float | None]:
		with self._lock:
			return self.started_at, self.last_client_seen

	def snapshot(self) -> dict[str, Any]:
		with self._lock:
			return {
				"status": self.status,
				"message": self.message,
				"overall": self.overall,
				"task": self.task,
				"error": self.error,
			}

	def begin_install(self) -> bool:
		with self._lock:
			if self._install_started or self.status == "running":
				return False
			self._install_started = True
			self.status = "running"
			self.message = tr("installer.status.starting_install")
			self.overall = 0.0
			self.task = 0.0
			self.error = ""
			return True

	def set_status(self, message: str):
		with self._lock:
			self.message = message

	def set_overall(self, value: float):
		with self._lock:
			self.overall = max(0.0, min(1.0, value))

	def set_task(self, value: float):
		with self._lock:
			self.task = max(0.0, min(1.0, value))

	def mark_done(self):
		with self._lock:
			self.status = "done"
			self.message = tr("installer.status.done")
			self.overall = 1.0
			self.task = 1.0

	def mark_error(self, detail: str):
		with self._lock:
			self.status = "error"
			self.error = detail
			self.message = tr("installer.status.failed")


def _static_path(rel: str) -> Path | None:
	candidate = (STATIC_DIR / rel).resolve()
	try:
		candidate.relative_to(STATIC_DIR.resolve())
	except ValueError:
		return None
	if not candidate.is_file():
		return None
	return candidate


def make_handler(session: InstallSession) -> type[BaseHTTPRequestHandler]:
	class Handler(BaseHTTPRequestHandler):
		def log_message(self, format: str, *args: Any):  # noqa: A003
			# Quiet successful GETs/POSTs; keep errors on stderr.
			if len(args) >= 2 and str(args[1]).startswith("2"):
				return
			sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

		def _token_ok(self) -> bool:
			parsed = urlparse(self.path)
			qs = parse_qs(parsed.query)
			token = (qs.get("t") or [None])[0]
			if not token:
				token = self.headers.get(TOKEN_HEADER)
			return bool(token) and secrets.compare_digest(str(token), session.token)

		def _send(self, code: int, body: bytes, *, content_type: str):
			self.send_response(code)
			self.send_header("Content-Type", content_type)
			self.send_header("Content-Length", str(len(body)))
			self.send_header("Cache-Control", "no-store")
			self.end_headers()
			self.wfile.write(body)

		def _send_json(self, code: int, payload: dict[str, Any]):
			raw = json.dumps(payload).encode("utf-8")
			self._send(code, raw, content_type="application/json; charset=utf-8")

		def _require_token(self) -> bool:
			if self._token_ok():
				session.touch_client()
				return True
			self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "invalid or missing token"})
			return False

		def do_GET(self):  # noqa: N802
			parsed = urlparse(self.path)
			path = parsed.path
			if path in {"/", "/index.html"}:
				if not self._require_token():
					return
				index = _static_path("index.html")
				if index is None:
					self._send_json(HTTPStatus.NOT_FOUND, {"error": "index missing"})
					return
				self._send(HTTPStatus.OK, index.read_bytes(), content_type="text/html; charset=utf-8")
				return
			if path.startswith("/static/"):
				# Static assets are non-secret; skip token so <link>/<script> work.
				rel = path.removeprefix("/static/")
				file_path = _static_path(rel)
				if file_path is None:
					self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
					return
				ctype, _ = mimetypes.guess_type(str(file_path))
				self._send(
					HTTPStatus.OK,
					file_path.read_bytes(),
					content_type=ctype or "application/octet-stream",
				)
				return
			if path == "/api/bootstrap":
				if not self._require_token():
					return
				self._send_json(
					HTTPStatus.OK,
					{
						"prefix": str(default_install_prefix()),
						"privacy_text": privacy_disclaimer_text(),
						"strings": {
							"window_title": tr("installer_online.window_title"),
							"subtitle": tr("installer_online.subtitle"),
							"prefix_label": tr("installer_online.prefix_label"),
							"privacy_title": tr("installer.privacy.title"),
							"privacy_ack": tr("installer.privacy.ack"),
							"install": tr("installer.button.install"),
							"finish": tr("installer_online.button.finish"),
							"ready": tr("installer.progress.ready"),
							"privacy_required": tr("installer.error.privacy_required"),
							"close_tab": tr("installer_online.close_tab"),
						},
					},
				)
				return
			if path == "/api/status":
				if not self._require_token():
					return
				self._send_json(HTTPStatus.OK, session.snapshot())
				return
			self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

		def do_POST(self):  # noqa: N802
			parsed = urlparse(self.path)
			path = parsed.path
			if not self._require_token():
				return
			length = int(self.headers.get("Content-Length", "0") or "0")
			raw = self.rfile.read(length) if length > 0 else b"{}"
			# sendBeacon / empty body → treat as {}
			if not raw.strip():
				payload: dict[str, Any] = {}
			else:
				try:
					decoded = json.loads(raw.decode("utf-8"))
				except (UnicodeDecodeError, json.JSONDecodeError):
					self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid JSON"})
					return
				if not isinstance(decoded, dict):
					self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid JSON object"})
					return
				payload = decoded

			if path == "/api/install":
				if not payload.get("privacy_ack"):
					self._send_json(
						HTTPStatus.BAD_REQUEST,
						{"error": tr("installer.error.privacy_required")},
					)
					return
				if not session.begin_install():
					self._send_json(HTTPStatus.CONFLICT, {"error": "install already started"})
					return
				prefix_raw = str(payload.get("prefix") or "").strip()
				prefix = Path(prefix_raw) if prefix_raw else None
				thread = threading.Thread(
					target=_run_install,
					args=(session, prefix),
					daemon=True,
				)
				thread.start()
				self._send_json(HTTPStatus.OK, {"ok": True})
				return

			if path == "/api/shutdown":
				print("Installer UI closed; shutting down.", file=sys.stderr)
				session.stop_event.set()
				self._send_json(HTTPStatus.OK, {"ok": True})
				return

			self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

	return Handler


def _client_watchdog(
	session: InstallSession,
	*,
	idle_seconds: float,
	grace_seconds: float,
):
	"""Stop the process when the browser tab stops heartbeating."""
	while not session.stop_event.wait(0.25):
		now = time.monotonic()
		started, last = session.client_activity()
		if last is None:
			if now - started >= grace_seconds:
				print(
					"No installer browser connected; shutting down.",
					file=sys.stderr,
				)
				session.stop_event.set()
				return
			continue
		if now - last >= idle_seconds:
			print(
				"Installer browser disconnected; shutting down.",
				file=sys.stderr,
			)
			session.stop_event.set()
			return


def _run_install(session: InstallSession, prefix: Path | None):
	try:
		options = build_online_install_options(prefix=prefix)

		def on_status(message: str):
			session.set_status(message)

		def on_task(index: int, total: int, label: str):
			fraction = (index / total) if total > 0 else 0.0
			session.set_overall(fraction)
			session.set_task(0.0)
			session.set_status(label)

		def on_progress(done: int, total: int, _label: str):
			if total <= 0:
				return
			session.set_task(min(1.0, max(0.0, done / total)))

		install_srxy(options, status=on_status, progress=on_progress, task=on_task)
		session.mark_done()
	except Exception as exc:
		detail = str(exc).strip() or traceback.format_exc()
		session.mark_error(detail)


def run_online_installer(
	*,
	open_browser: bool = True,
	serve_forever: bool = True,
	on_ready: Callable[[str, InstallSession, ThreadingHTTPServer], None] | None = None,
	client_idle_seconds: float = DEFAULT_CLIENT_IDLE_SECONDS,
	client_grace_seconds: float = DEFAULT_CLIENT_GRACE_SECONDS,
	client_watchdog: bool = True,
	url_file: Path | None = None,
) -> int:
	"""Serve the installer UI on 127.0.0.1 and optionally open a browser."""
	set_language(resolve_language())
	token = secrets.token_urlsafe(24)
	session = InstallSession(token=token)
	handler = make_handler(session)
	server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
	host, port = server.server_address[:2]
	url = f"http://{host}:{port}/?t={token}"

	thread = threading.Thread(target=server.serve_forever, daemon=True)
	thread.start()

	if client_watchdog:
		watchdog = threading.Thread(
			target=_client_watchdog,
			args=(session,),
			kwargs={
				"idle_seconds": client_idle_seconds,
				"grace_seconds": client_grace_seconds,
			},
			daemon=True,
		)
		watchdog.start()

	if url_file is not None:
		url_file.parent.mkdir(parents=True, exist_ok=True)
		url_file.write_text(url + "\n", encoding="utf-8")

	if on_ready is not None:
		on_ready(url, session, server)

	if open_browser:
		open_installer_url(url)
	else:
		print(url, file=sys.stderr)

	if not serve_forever:
		return 0

	try:
		session.stop_event.wait()
	except KeyboardInterrupt:
		session.stop_event.set()
	finally:
		server.shutdown()
		thread.join(timeout=5)
	return 0


__all__ = [
	"DEFAULT_CLIENT_GRACE_SECONDS",
	"DEFAULT_CLIENT_IDLE_SECONDS",
	"InstallSession",
	"TOKEN_HEADER",
	"make_handler",
	"run_online_installer",
]
