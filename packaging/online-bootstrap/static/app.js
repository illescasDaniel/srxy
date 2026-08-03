(() => {
	const params = new URLSearchParams(window.location.search);
	const token = params.get("t") || "";
	const statusEl = document.getElementById("status");
	const errorEl = document.getElementById("error");
	const barEl = document.getElementById("bar");
	let redirecting = false;
	let finished = false;

	function apiUrl(path) {
		const url = new URL(path, window.location.origin);
		url.searchParams.set("t", token);
		return url.toString();
	}

	function requestShutdown() {
		if (finished || redirecting) {
			return;
		}
		finished = true;
		const body = "{}";
		const url = apiUrl("/api/shutdown");
		try {
			if (navigator.sendBeacon) {
				navigator.sendBeacon(url, new Blob([body], { type: "application/json" }));
			}
		} catch (_err) {
			/* ignore */
		}
	}

	window.addEventListener("pagehide", () => {
		requestShutdown();
	});

	async function poll() {
		if (!token || finished || redirecting) {
			return;
		}
		try {
			const res = await fetch(apiUrl("/api/boot-status"), {
				headers: { "X-Srxy-Installer-Token": token },
			});
			const data = await res.json();
			if (!res.ok) {
				throw new Error(data.error || `HTTP ${res.status}`);
			}
			statusEl.textContent = data.message || data.phase || "";
			const pct = Math.max(0, Math.min(100, Math.round((data.progress || 0) * 100)));
			barEl.style.width = `${pct}%`;
			if (data.error) {
				errorEl.hidden = false;
				errorEl.textContent = data.error;
			}
			if (data.redirect_url) {
				redirecting = true;
				window.location.replace(data.redirect_url);
				return;
			}
		} catch (err) {
			statusEl.textContent = err.message || String(err);
		}
	}

	if (!token) {
		statusEl.textContent = "Missing token.";
		return;
	}
	poll();
	window.setInterval(poll, 400);
})();
