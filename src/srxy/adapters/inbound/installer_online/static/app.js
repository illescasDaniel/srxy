(() => {
	const params = new URLSearchParams(window.location.search);
	const token = params.get("t") || "";

	const els = {
		subtitle: document.getElementById("subtitle"),
		prefixLabel: document.getElementById("prefix-label"),
		prefix: document.getElementById("prefix"),
		privacyTitle: document.getElementById("privacy-title"),
		privacy: document.getElementById("privacy"),
		privacyAck: document.getElementById("privacy-ack"),
		ack: document.getElementById("ack"),
		status: document.getElementById("status"),
		overall: document.getElementById("overall-bar"),
		task: document.getElementById("task-bar"),
		install: document.getElementById("install"),
		uninstall: document.getElementById("uninstall"),
		finish: document.getElementById("finish"),
		launch: document.getElementById("launch"),
		closeHint: document.getElementById("close-hint"),
	};

	let strings = {};
	let busy = false;
	let done = false;
	let finished = false;
	let canLaunch = false;
	let pollTimer = null;

	function apiUrl(path) {
		const url = new URL(path, window.location.origin);
		url.searchParams.set("t", token);
		return url.toString();
	}

	async function api(path, options = {}) {
		const headers = Object.assign(
			{ "X-Srxy-Installer-Token": token },
			options.headers || {},
		);
		const response = await fetch(apiUrl(path), Object.assign({}, options, { headers }));
		const data = await response.json().catch(() => ({}));
		if (!response.ok) {
			const err = new Error(data.error || `HTTP ${response.status}`);
			err.status = response.status;
			err.data = data;
			throw err;
		}
		return data;
	}

	function setBar(el, value) {
		const pct = Math.max(0, Math.min(100, Math.round((value || 0) * 100)));
		el.style.width = `${pct}%`;
	}

	function refreshActionEnabled() {
		els.install.disabled = busy || done || finished || !els.ack.checked;
		els.uninstall.disabled = busy || done || finished;
		els.launch.hidden = !canLaunch;
		els.launch.disabled = busy || finished || !canLaunch;
	}

	function applyStrings(s) {
		strings = s || {};
		document.title = strings.window_title || document.title;
		els.subtitle.textContent = strings.subtitle || "";
		els.prefixLabel.textContent = strings.prefix_label || "";
		els.privacyTitle.textContent = strings.privacy_title || "";
		els.privacyAck.textContent = strings.privacy_ack || "";
		els.install.textContent = strings.install || "Install";
		els.uninstall.textContent = strings.uninstall || "Uninstall";
		els.finish.textContent = strings.finish || "Finish";
		els.launch.textContent = strings.launch || "Launch";
		els.status.textContent = strings.ready || "";
		els.closeHint.textContent = strings.close_tab || "";
	}

	function applyStatus(snap) {
		if (finished) {
			return;
		}
		els.status.textContent = snap.message || "";
		els.status.classList.toggle("error", snap.status === "error");
		if (snap.error) {
			els.status.textContent = `${snap.message || ""} ${snap.error}`.trim();
		}
		setBar(els.overall, snap.overall);
		setBar(els.task, snap.task);
		if (snap.status === "running") {
			busy = true;
			canLaunch = false;
			els.finish.disabled = true;
			refreshActionEnabled();
		}
		if (snap.status === "done" || snap.status === "error") {
			busy = false;
			done = snap.status === "done";
			canLaunch = Boolean(snap.can_launch);
			els.finish.disabled = false;
			refreshActionEnabled();
		}
	}

	function startHeartbeat() {
		stopHeartbeat();
		pollTimer = window.setInterval(async () => {
			if (finished) {
				return;
			}
			try {
				const snap = await api("/api/status");
				applyStatus(snap);
			} catch (_err) {
				/* keep heartbeating until shutdown */
			}
		}, 400);
	}

	function stopHeartbeat() {
		if (pollTimer !== null) {
			window.clearInterval(pollTimer);
			pollTimer = null;
		}
	}

	function requestShutdown() {
		if (finished) {
			return;
		}
		finished = true;
		stopHeartbeat();
		els.finish.disabled = true;
		els.launch.disabled = true;
		els.install.disabled = true;
		els.uninstall.disabled = true;
		const body = "{}";
		const url = apiUrl("/api/shutdown");
		try {
			if (navigator.sendBeacon) {
				const blob = new Blob([body], { type: "application/json" });
				navigator.sendBeacon(url, blob);
			} else {
				fetch(url, {
					method: "POST",
					headers: {
						"Content-Type": "application/json",
						"X-Srxy-Installer-Token": token,
					},
					body,
					keepalive: true,
				}).catch(() => {});
			}
		} catch (_err) {
			/* ignore */
		}
		els.closeHint.hidden = false;
	}

	els.ack.addEventListener("change", refreshActionEnabled);

	els.install.addEventListener("click", async () => {
		if (busy || done || finished || !els.ack.checked) {
			els.status.textContent = strings.privacy_required || "";
			return;
		}
		busy = true;
		canLaunch = false;
		refreshActionEnabled();
		els.finish.disabled = true;
		try {
			await api("/api/install", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					privacy_ack: true,
					prefix: els.prefix.value.trim(),
				}),
			});
		} catch (err) {
			busy = false;
			refreshActionEnabled();
			els.status.textContent = err.message || String(err);
			els.status.classList.add("error");
		}
	});

	els.uninstall.addEventListener("click", async () => {
		if (busy || done || finished) {
			return;
		}
		const message = strings.confirm_uninstall || "Remove srxy from this folder?";
		if (!window.confirm(message)) {
			return;
		}
		busy = true;
		canLaunch = false;
		refreshActionEnabled();
		els.finish.disabled = true;
		try {
			await api("/api/uninstall", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					prefix: els.prefix.value.trim(),
				}),
			});
		} catch (err) {
			busy = false;
			refreshActionEnabled();
			els.status.textContent = err.message || String(err);
			els.status.classList.add("error");
		}
	});

	els.finish.addEventListener("click", () => {
		requestShutdown();
	});

	els.launch.addEventListener("click", async () => {
		if (busy || finished || !canLaunch) {
			return;
		}
		busy = true;
		refreshActionEnabled();
		try {
			await api("/api/launch", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: "{}",
			});
			finished = true;
			stopHeartbeat();
			els.finish.disabled = true;
			els.launch.disabled = true;
			els.install.disabled = true;
			els.uninstall.disabled = true;
			els.closeHint.hidden = false;
		} catch (err) {
			busy = false;
			refreshActionEnabled();
			els.status.textContent = err.message || String(err);
			els.status.classList.add("error");
		}
	});

	window.addEventListener("pagehide", () => {
		requestShutdown();
	});
	window.addEventListener("beforeunload", () => {
		requestShutdown();
	});

	async function boot() {
		if (!token) {
			els.status.textContent = "Missing installer token. Open the URL printed by the installer.";
			els.status.classList.add("error");
			return;
		}
		const boot = await api("/api/bootstrap");
		applyStrings(boot.strings);
		els.prefix.value = boot.prefix || "";
		els.privacy.textContent = boot.privacy_text || "";
		refreshActionEnabled();
		startHeartbeat();
	}

	boot().catch((err) => {
		els.status.textContent = err.message || String(err);
		els.status.classList.add("error");
	});
})();
