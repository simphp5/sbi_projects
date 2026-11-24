# SBI Office – quick update (app page, icons, install-as-app file). System Console -> Python -> tick Commit -> Execute.
OFFICE_HTML = r'''<div id="sbo" class="sbo"><div class="sbo-boot"><div class="sbo-spin"></div><div>Opening SBI Office…</div></div></div>'''
OFFICE_CSS = r'''/* SBI Office - staff punch app (web page /sbi_office). Hides the website chrome so it looks like an app. */
body.sbo-body { background: #f3f4f6 !important; margin: 0; }
body.sbo-body .navbar, body.sbo-body header.navbar, body.sbo-body .web-footer, body.sbo-body footer, body.sbo-body .page-breadcrumbs,
body.sbo-body .page-header-wrapper, body.sbo-body .page-header, body.sbo-body .web-sidebar, body.sbo-body .banner { display: none !important; }
body.sbo-body .page-content-wrapper, body.sbo-body main, body.sbo-body .container, body.sbo-body .page_content, body.sbo-body .page-container,
body.sbo-body .web-page-content, body.sbo-body .from-markdown { max-width: 100% !important; width: 100% !important; padding: 0 !important; margin: 0 !important; }
.sbo { --red: #c8102e; --red-d: #8f0b20; --ink: #1f2937; --mut: #6b7280; --line: #e5e7eb; --card: #fff; --bg: #f3f4f6; --green: #16a34a; --amber: #d97706;
  font-family: Inter, -apple-system, "Segoe UI", Roboto, Arial, sans-serif; color: var(--ink); max-width: 560px; margin: 0 auto; min-height: 100vh;
  background: var(--bg); padding-bottom: 84px; font-size: 14px; -webkit-tap-highlight-color: transparent; }
.sbo * { box-sizing: border-box; }
.sbo-boot { min-height: 70vh; display: grid; place-items: center; align-content: center; gap: 12px; color: var(--mut); }
.sbo-spin { width: 34px; height: 34px; border-radius: 50%; border: 3px solid #fecdd3; border-top-color: var(--red); animation: sbospin 0.9s linear infinite; }
@keyframes sbospin { to { transform: rotate(360deg); } }
.sbo-top { position: sticky; top: 0; z-index: 5; display: flex; align-items: center; gap: 10px; padding: 12px 14px; color: #fff;
  background: linear-gradient(120deg, var(--red-d), var(--red) 65%, #e0485e); box-shadow: 0 4px 14px rgba(143,11,32,.25); }
.sbo-logo { width: 38px; height: 38px; border-radius: 10px; background: #fff; display: grid; place-items: center; overflow: hidden; flex: none; }
.sbo-logo img { max-width: 34px; max-height: 34px; }
.sbo-brand b { display: block; font-size: 17px; letter-spacing: .2px; }
.sbo-brand span { font-size: 11.5px; opacity: .9; }
.sbo-clock { margin-left: auto; text-align: right; font-variant-numeric: tabular-nums; }
.sbo-clock b { display: block; font-size: 20px; }
.sbo-clock span { font-size: 11px; opacity: .9; }
.sbo-wrap { padding: 12px; }
.sbo-card { background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 14px; margin-bottom: 12px; box-shadow: 0 1px 2px rgba(0,0,0,.03); }
.sbo-card h3 { margin: 0 0 10px; font-size: 15px; display: flex; align-items: center; gap: 8px; }
.sbo-card h3 .sbo-mut { font-weight: 400; margin-left: auto; }
.sbo-mut { color: var(--mut); font-size: 12.5px; }
.sbo-who { display: flex; align-items: center; gap: 12px; }
.sbo-av { width: 50px; height: 50px; border-radius: 50%; background: #fde2e6; color: var(--red); display: grid; place-items: center; font-weight: 800; font-size: 18px; overflow: hidden; flex: none; }
.sbo-av img { width: 100%; height: 100%; object-fit: cover; }
.sbo-name { font-weight: 800; font-size: 16px; }
.sbo-shift { display: flex; gap: 8px; margin-top: 12px; }
.sbo-shift div { flex: 1; background: var(--bg); border-radius: 12px; padding: 8px 10px; }
.sbo-shift b { display: block; font-size: 16px; font-variant-numeric: tabular-nums; }
.sbo-shift span { font-size: 11px; color: var(--mut); }
.sbo-gps { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border-radius: 12px; background: var(--bg); margin-top: 12px; font-size: 13px; line-height: 1.35; }
.sbo-dot { width: 10px; height: 10px; border-radius: 50%; background: #9ca3af; flex: none; }
.sbo-dot.ok { background: var(--green); box-shadow: 0 0 0 4px rgba(22,163,74,.15); } .sbo-dot.warn { background: var(--amber); } .sbo-dot.bad { background: var(--red); }
.sbo-punch { display: grid; place-items: center; padding: 18px 0 6px; }
.sbo-ring { width: 196px; height: 196px; border-radius: 50%; border: 0; cursor: pointer; color: #fff; display: grid; place-items: center; align-content: center; gap: 4px;
  background: radial-gradient(circle at 35% 30%, #4ade80, #16a34a 60%, #15803d); box-shadow: 0 12px 30px rgba(22,163,74,.35), inset 0 -6px 14px rgba(0,0,0,.15);
  font-family: inherit; transition: transform .12s; }
.sbo-ring:active { transform: scale(.96); }
.sbo-ring.out { background: radial-gradient(circle at 35% 30%, #f87171, #c8102e 60%, #8f0b20); box-shadow: 0 12px 30px rgba(200,16,46,.35), inset 0 -6px 14px rgba(0,0,0,.15); }
.sbo-ring.off span { opacity: 1; }
.sbo-ring.off { background: radial-gradient(circle at 35% 30%, #d1d5db, #9ca3af 60%, #6b7280); box-shadow: none; }
.sbo-ring svg { width: 46px; height: 46px; }
.sbo-ring b { font-size: 24px; letter-spacing: .5px; }
.sbo-ring span { font-size: 12px; opacity: .9; }
.sbo-note { text-align: center; margin-top: 8px; }
.sbo-toast.sbo-banner { font-size: 13.5px; }
.sbo-banner { display: flex; align-items: center; gap: 10px; border-radius: 12px; padding: 10px 12px; margin-bottom: 12px; font-size: 13px; }
.sbo-banner.info { background: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe; }
.sbo-banner.warn { background: #fff7ed; color: #9a3412; border: 1px solid #fed7aa; }
.sbo-banner.ok { background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; }
.sbo-banner .sbo-btn { margin-left: auto; flex: none; }
.sbo-btn { border: 1px solid var(--line); background: var(--card); color: var(--ink); border-radius: 10px; padding: 9px 14px; font-size: 13.5px; cursor: pointer; font-family: inherit; }
.sbo-btn.pri { background: var(--red); border-color: var(--red); color: #fff; font-weight: 700; }
.sbo-btn.sm { padding: 6px 10px; font-size: 12px; }
.sbo input, .sbo select { width: 100%; border: 1px solid var(--line); border-radius: 10px; padding: 9px 10px; font-size: 14px; background: #fff; color: var(--ink); font-family: inherit; }
.sbo label { display: block; font-size: 12px; color: var(--mut); margin-top: 8px; }
.sbo-row { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; align-items: center; }
.sbo-tl { list-style: none; margin: 0; padding: 0; }
.sbo-tl li { display: flex; align-items: center; gap: 10px; padding: 9px 0; border-bottom: 1px dashed var(--line); }
.sbo-tl li:last-child { border-bottom: 0; }
.sbo-tag { font-size: 11px; font-weight: 800; padding: 3px 8px; border-radius: 999px; background: #dcfce7; color: #166534; min-width: 42px; text-align: center; }
.sbo-tag.out { background: #fee2e2; color: #991b1b; }
.sbo-tl .t { font-weight: 800; font-variant-numeric: tabular-nums; }
.sbo-tl .m { margin-left: auto; font-size: 12px; color: var(--mut); text-align: right; }
.sbo a { color: var(--red); text-decoration: none; }
.sbo-tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.sbo-tbl th { text-align: left; font-size: 10.5px; color: var(--mut); text-transform: uppercase; letter-spacing: .4px; padding: 6px 4px; border-bottom: 1px solid var(--line); }
.sbo-tbl td { padding: 8px 4px; border-bottom: 1px solid var(--line); vertical-align: top; }
.sbo-tbl .r { text-align: right; }
.sbo-pill { font-size: 11px; padding: 2px 8px; border-radius: 999px; background: var(--bg); white-space: nowrap; }
.sbo-pill.g { background: #dcfce7; color: #166534; } .sbo-pill.r { background: #fee2e2; color: #991b1b; } .sbo-pill.a { background: #fef3c7; color: #92400e; }
.sbo-sum { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 10px; }
.sbo-sum div { background: var(--bg); border-radius: 12px; padding: 8px 10px; }
.sbo-sum b { display: block; font-size: 17px; }
.sbo-sum span { font-size: 11px; color: var(--mut); }
.sbo-nav { position: fixed; bottom: 0; left: 0; right: 0; z-index: 6; display: flex; justify-content: center; background: #fff; border-top: 1px solid var(--line);
  padding: 6px 0 calc(6px + env(safe-area-inset-bottom)); }
.sbo-nav a { flex: 1; max-width: 186px; text-align: center; color: var(--mut); font-size: 11.5px; padding: 4px 0; cursor: pointer; }
.sbo-nav a svg { width: 22px; height: 22px; display: block; margin: 0 auto 2px; }
.sbo-nav a.on { color: var(--red); font-weight: 700; }
/* full-screen camera: whole picture shown (no zoom), controls below */
.sbo-cam, .sbo-done, .sbo-toast { font-family: Inter, -apple-system, "Segoe UI", Roboto, Arial, sans-serif; -webkit-font-smoothing: antialiased; }
.sbo-cam { position: fixed; inset: 0; z-index: 50; background: #0b0b0c; display: flex; flex-direction: column; color: #fff; }
.sbo-cam-top { display: flex; align-items: center; gap: 10px; padding: 10px 14px; flex: none; }
.sbo-cam-top b { font-size: 16px; }
.sbo-stage { position: relative; flex: 1 1 auto; min-height: 0; display: grid; place-items: center; overflow: hidden; }
.sbo-stage video, .sbo-stage img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; display: block; background: #000; }
.sbo-stage video { transform: scaleX(-1); }
.sbo-oval { position: absolute; left: 50%; top: 47%; height: 84%; max-height: 640px; max-width: 86%; aspect-ratio: 3 / 4; transform: translate(-50%, -50%);
  border: 3px dashed rgba(255,255,255,.85); border-radius: 50%; pointer-events: none; box-shadow: 0 0 0 200vmax rgba(0,0,0,.22); }
.sbo-arrow { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 64px; color: #fde68a; text-shadow: 0 2px 10px rgba(0,0,0,.6);
  pointer-events: none; animation: sbopulse 1s ease-in-out infinite alternate; }
@keyframes sbopulse { from { opacity: .45; } to { opacity: 1; } }
.sbo-cam-msg { flex: none; text-align: center; font-size: 13.5px; padding: 8px 14px 4px; line-height: 1.4; }
.sbo-thumbs { flex: none; display: flex; justify-content: center; gap: 10px; padding: 6px 0; }
.sbo-th { width: 64px; height: 80px; border-radius: 10px; border: 2px dashed rgba(255,255,255,.4); display: grid; place-items: center; position: relative; overflow: hidden; cursor: pointer; font-size: 22px; }
.sbo-th.ok { border: 2px solid #22c55e; }
.sbo-th img { width: 100%; height: 100%; object-fit: cover; }
.sbo-th i { position: absolute; bottom: 0; left: 0; right: 0; font-style: normal; font-size: 10px; text-align: center; background: rgba(0,0,0,.55); text-transform: uppercase; letter-spacing: .5px; }
.sbo-cam-low { flex: none; padding: 0 12px calc(12px + env(safe-area-inset-bottom)); }
.sbo-cam-reason input { background: rgba(255,255,255,.95); margin-bottom: 6px; }
.sbo-cam-gps { background: rgba(255,255,255,.08); border-radius: 12px; padding: 8px 12px; font-size: 12.5px; display: flex; gap: 8px; align-items: flex-start; line-height: 1.4; }
.sbo-cam-gps .sbo-dot { margin-top: 4px; }
.sbo-cam-bar { display: flex; align-items: center; justify-content: space-around; padding: 12px 0 2px; }
.sbo-cam-bar .sbo-btn { background: rgba(255,255,255,.14); color: #fff; border-color: rgba(255,255,255,.3); min-width: 88px; }
.sbo-cam-bar .sbo-btn.pri { background: var(--green, #16a34a); border-color: transparent; }
.sbo-shutter { width: 74px; height: 74px; border-radius: 50%; border: 5px solid #fff; background: #16a34a; cursor: pointer; }
.sbo-shutter.out { background: #c8102e; }
.sbo-shutter.enroll { background: #2563eb; }
.sbo-shutter:disabled { opacity: .35; }
.sbo-faces { display: flex; gap: 8px; }
.sbo-faces a { position: relative; width: 33%; max-width: 120px; aspect-ratio: 3 / 4; border-radius: 12px; overflow: hidden; background: var(--bg); }
.sbo-faces img { width: 100%; height: 100%; object-fit: cover; }
.sbo-faces i { position: absolute; bottom: 0; left: 0; right: 0; font-style: normal; font-size: 10.5px; text-align: center; color: #fff; background: rgba(0,0,0,.5); text-transform: uppercase; }
@media (min-width: 900px) { .sbo-stage { margin: 0 8vw; } }
/* success */
.sbo-done { position: fixed; inset: 0; z-index: 60; display: grid; place-items: center; align-content: center; gap: 10px; color: #fff; text-align: center; padding: 20px;
  background: rgba(22,163,74,.96); animation: sbofade .2s ease-out; }
.sbo-done.out { background: rgba(200,16,46,.96); }
.sbo-done .tick { width: 96px; height: 96px; border-radius: 50%; background: #fff; color: var(--green); display: grid; place-items: center; font-size: 56px; font-weight: 900; }
.sbo-done.out .tick { color: var(--red); }
.sbo-done b { font-size: 26px; }
.sbo-done img { width: min(78vw, 420px); max-height: 52vh; border-radius: 14px; object-fit: contain; border: 4px solid #fff; background: #000; }
@keyframes sbofade { from { opacity: 0; transform: scale(1.04); } to { opacity: 1; transform: none; } }
.hide { display: none !important; }
@media (min-width: 700px) { .sbo { border-left: 1px solid var(--line); border-right: 1px solid var(--line); } }

/* camera zoom */
.sbo-zoombar { position: absolute; left: 50%; bottom: 10px; transform: translateX(-50%); z-index: 3; display: flex; flex-wrap: wrap; align-items: center; gap: 6px 8px;
  background: rgba(0,0,0,.6); border-radius: 18px; padding: 6px 12px; width: min(92%, 400px); }
.sbo-zp { display: flex; justify-content: center; gap: 6px; width: 100%; }
.sbo-zp button { width: auto !important; height: 28px !important; border-radius: 999px !important; padding: 0 10px; font-size: 12.5px !important; font-weight: 700; }
.sbo-zp button.on { background: #fde68a !important; color: #111 !important; border-color: #fde68a !important; }
.sbo-zoombar button { width: 34px; height: 34px; border-radius: 50%; border: 1px solid rgba(255,255,255,.45); background: rgba(255,255,255,.12); color: #fff;
  font-size: 20px; line-height: 1; cursor: pointer; flex: none; }
.sbo-zoombar input[type=range] { flex: 1; accent-color: #fff; width: auto; padding: 0; border: 0; background: transparent; }
.sbo-zoombar b { font-size: 12.5px; min-width: 34px; text-align: right; color: #fff; }
.sbo-stage video { transition: transform .08s linear; transform-origin: center center; }
.sbo-stage video { background: transparent; }'''
OFFICE_JS = r'''// SBI Office - office staff punch app (web page /sbi_office). Punch IN / OUT with GPS + selfie, reminders before office time.
(function () {
	const API = "sbi_office_punch", APP = "/sbi_office";
	const SW = "/files/sbi_office_sw.js", MANIFEST = "/files/sbi_office_manifest_v2.json", APPICON = "/files/sbi_office_icon_180.png", APK = "/files/SBI-Office-v1.0.apk";
	const S = { d: null, pos: null, gpsErr: "", stream: null, shot: "", watch: null, tab: "punch", csrf: "", month: null, back: 0, busy: false };
	const $ = (s) => document.querySelector(s);
	const esc = (v) => String(v === null || v === undefined ? "" : v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
	const km = (m) => (m >= 1000 ? (m / 1000).toFixed(2) + " km" : Math.round(m) + " m");
	const pad = (n) => ("0" + n).slice(-2);
	const ymd = (d) => d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
	const dmy = (s) => (s ? s.slice(8, 10) + "-" + s.slice(5, 7) + "-" + s.slice(0, 4) : "");
	const ICON = {
		finger: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M12 11v3a8 8 0 0 1-1.5 4.7"/><path d="M8.5 9.5A4 4 0 0 1 16 11v2c0 2.4-.6 4.6-1.6 6.5"/><path d="M5.6 7.5A7 7 0 0 1 19 11v1.5"/><path d="M5 12v1a11 11 0 0 0 .9 4.4"/><path d="M8 12.5v.5a12 12 0 0 1-1 4.8"/></svg>`,
		home: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>`,
		cal: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>`,
		team: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><circle cx="17" cy="9" r="2.5"/><path d="M16 14.2a5 5 0 0 1 5.5 4.8"/></svg>`,
	};

	// ---------------------------------------------------------------- login + page setup
	function cookie(n) { const m = document.cookie.match("(^|;)\\s*" + n + "=([^;]*)"); return m ? decodeURIComponent(m[2]) : ""; }
	const who = cookie("user_id");
	if (!who || who === "Guest") { window.location.href = "/login?redirect-to=" + encodeURIComponent(APP); return; }
	document.body.classList.add("sbo-body");
	document.title = "SBI Office";
	[["manifest", MANIFEST], ["apple-touch-icon", APPICON], ["icon", APPICON]].forEach((x) => {
		const l = document.createElement("link"); l.rel = x[0]; l.href = x[1]; document.head.appendChild(l);
	});
	const IOS = /iphone|ipad|ipod/i.test(navigator.userAgent || "") || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
	const STANDALONE = window.navigator.standalone === true || (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches);
	[["theme-color", "#c8102e"], ["mobile-web-app-capable", "yes"], ["apple-mobile-web-app-capable", "yes"], ["apple-mobile-web-app-title", "SBI Office"], ["apple-mobile-web-app-status-bar-style", "black-translucent"]].forEach((m) => {
		const t = document.createElement("meta"); t.name = m[0]; t.content = m[1]; document.head.appendChild(t);
	});
	let swReg = null;
	if ("serviceWorker" in navigator) {
		navigator.serviceWorker.register(SW, { scope: "/files/" }).then((r) => { swReg = r; }).catch(() => { /* reminders still work while the app is open */ });
	}

	// ---------------------------------------------------------------- server calls (CSRF-safe)
	async function token(fresh) {
		if (!fresh) {
			if (S.csrf) return S.csrf;
			if (window.frappe && window.frappe.csrf_token && window.frappe.csrf_token.indexOf("{") < 0) return window.frappe.csrf_token;
		}
		try {
			const t = await fetch(APP + "?_=" + Date.now(), { credentials: "same-origin", cache: "no-store" }).then((r) => r.text());
			const m = t.match(/csrf_token\s*[=:]\s*["']([^"'{}]+)["']/);
			S.csrf = m ? m[1] : "";
		} catch (e) { S.csrf = ""; }
		return S.csrf;
	}
	function serverMsg(j) {
		try {
			if (j._server_messages) return JSON.parse(j._server_messages).map((x) => { try { return JSON.parse(x).message; } catch (e) { return x; } }).join(" ").replace(/<[^>]+>/g, "");
		} catch (e) { /* ignore */ }
		return (j.exception || j.message || "Something went wrong").toString().replace(/^.*?Error:\s*/, "");
	}
	async function call(act, args, retried) {
		const base = { act: act };
		if (S.asEmp) base.as_employee = S.asEmp;
		const body = new URLSearchParams(Object.assign(base, args || {}));
		const r = await fetch("/api/method/" + API, { method: "POST", credentials: "same-origin", body: body,
			headers: { "Accept": "application/json", "X-Frappe-CSRF-Token": await token(retried), "X-Requested-With": "XMLHttpRequest" } });
		let j = {};
		try { j = await r.json(); } catch (e) { /* not json */ }
		if (!retried && r.status === 400 && /csrf/i.test(JSON.stringify(j))) return call(act, args, true);
		if (r.status === 401 || (r.status === 403 && /login|guest/i.test(JSON.stringify(j)))) { window.location.href = "/login?redirect-to=" + encodeURIComponent(APP); throw new Error("login"); }
		if (!r.ok) throw new Error(serverMsg(j));
		return j.message || {};
	}
	function toast(msg, kind) {
		const t = document.createElement("div");
		t.className = "sbo-toast sbo-banner " + (kind || "warn");
		t.style.cssText = "position:fixed;left:12px;right:12px;bottom:86px;z-index:70;max-width:536px;margin:0 auto;box-shadow:0 8px 24px rgba(0,0,0,.18)";
		t.innerHTML = esc(msg);
		document.body.appendChild(t);
		setTimeout(() => t.remove(), 6000);
	}

	// ---------------------------------------------------------------- GPS
	function distTo(o, p) {
		if (!o || !o.set || !p) return null;
		const k = Math.PI / 180, dLat = (p.lat - o.lat) * k, dLng = (p.lng - o.lng) * k;
		const a = Math.sin(dLat / 2) ** 2 + Math.cos(o.lat * k) * Math.cos(p.lat * k) * Math.sin(dLng / 2) ** 2;
		return 6371000 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
	}
	// street / area / city for the current location (OpenStreetMap, then BigDataCloud as a backup)
	const ADDR = { key: "", busy: false, at: null };
	const JUNK = /^(ward|zone|division|block)\s*(no\.?)?\s*\d+/i;
	const clean = (v) => String(v || "").replace(/^zone\s*\d+\s*/i, "").trim();
	const good = (v) => !!v && !JUNK.test(String(v).trim());
	function uniq(list) {
		const seen = {}, out = [];
		list.forEach((v) => { v = clean(v); const k = v.toLowerCase(); if (v && good(v) && !seen[k]) { seen[k] = 1; out.push(v); } });
		return out;
	}
	function addrText(a) {
		if (!a) return "";
		return uniq([a.place, a.street, a.area, a.locality, a.city]).join(", ") + (a.pin ? " – " + a.pin : "");
	}
	async function overpass(q) {
		for (const host of ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]) {
			const ctl = window.AbortController ? new AbortController() : null;
			const tm = setTimeout(() => { try { ctl && ctl.abort(); } catch (e) { /* ignore */ } }, 7000);
			try {
				const r = await fetch(host, { method: "POST", signal: ctl ? ctl.signal : undefined, body: "data=" + encodeURIComponent(q), headers: { "Content-Type": "application/x-www-form-urlencoded" } });
				clearTimeout(tm);
				if (r.ok) return await r.json();
			} catch (e) { clearTimeout(tm); /* slow or down: try the next server */ }
		}
		return null;
	}
	async function nearbyPlace(p) {
		// 1) the building you are standing INSIDE (its outline contains your GPS point)
		const ll = p.lat + "," + p.lng;
		const inside = await overpass("[out:json][timeout:8];is_in(" + ll + ")->.a;(way(pivot.a)[building][name];relation(pivot.a)[building][name];" +
			"way(pivot.a)[name][amenity];way(pivot.a)[name][office];way(pivot.a)[name][landuse=commercial];);out tags 5;");
		const own = ((inside && inside.elements) || []).find((e) => e.tags && e.tags.name && (e.tags.building || e.tags.office));
		const any = ((inside && inside.elements) || []).find((e) => e.tags && e.tags.name);
		if (own || any) return { name: (own || any).tags.name, inside: true };
		// 2) otherwise the closest named building / office within 25 m, shown as "near ..."
		const r = Math.max(15, Math.min(25, p.acc || 25));
		const j = await overpass("[out:json][timeout:8];(nwr(around:" + r + "," + ll + ")[name][building];nwr(around:" + r + "," + ll + ")[name][office];);out tags center 10;");
		let best = null, bd = 1e9;
		((j && j.elements) || []).forEach((e) => {
			const la = e.lat || (e.center && e.center.lat), lo = e.lon || (e.center && e.center.lon);
			if (!la || !e.tags || !e.tags.name) return;
			const dd = distTo({ set: 1, lat: la, lng: lo }, p);
			if (dd < bd) { bd = dd; best = e.tags.name; }
		});
		return best ? { name: best, inside: false } : null;
	}
	async function geocode(force) {
		const p = S.pos;
		if (!p || ADDR.busy) return;
		if (!force && ADDR.at && distTo({ set: 1, lat: ADDR.at.lat, lng: ADDR.at.lng }, p) < 40 && !(ADDR.at.acc > 60 && p.acc < ADDR.at.acc / 2)) return;
		ADDR.busy = true;
		let a = null;
		try {
			const u = "https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=18&addressdetails=1&namedetails=1&accept-language=en&lat=" + p.lat + "&lon=" + p.lng;
			const ctl = window.AbortController ? new AbortController() : null;
			const tm = setTimeout(() => { try { ctl && ctl.abort(); } catch (e) { /* ignore */ } }, 8000);
			const j = await fetch(u, { headers: { "Accept": "application/json" }, signal: ctl ? ctl.signal : undefined }).then((r) => r.json()).finally(() => clearTimeout(tm));
			const x = j.address || {};
			let named = ["building", "amenity", "shop", "office", "tourism", "leisure", "healthcare", "craft"].indexOf(j.category) >= 0 ? j.name : "";
			const objD = j.lat ? distTo({ set: 1, lat: Number(j.lat), lng: Number(j.lon) }, p) : 0;
			if (named && objD > 20 && j.category !== "building") named = "";
			// pieces from the long name, without "Ward 178" / "Zone 13" parts
			const parts = String(j.display_name || "").split(",").map((s) => s.trim());
			a = {
				place: named || (objD <= 20 ? (x.building || x.office || x.amenity || "") : "") || x.residential || x.commercial || x.industrial || "",
				street: [x.house_number, x.road || x.pedestrian || x.footway || x.street].filter(Boolean).join(" "),
				area: [x.neighbourhood, x.quarter, x.residential, x.hamlet, x.village].find(good) || "",
				locality: [x.county, x.city_district, x.suburb, x.town].map(clean).find(good) || "",
				city: [x.city, x.town, x.municipality, x.state_district].map(clean).find(good) || "",
				state: x.state || "", pin: x.postcode || "", full: parts.filter(good).join(", "),
			};
			if (a.area && a.locality && a.area.toLowerCase() === a.locality.toLowerCase()) a.area = "";
		} catch (e) { a = null; }
		if (!a || !(a.street || a.area || a.locality || a.city)) {
			try {
				const j = await fetch("https://api.bigdatacloud.net/data/reverse-geocode-client?localityLanguage=en&latitude=" + p.lat + "&longitude=" + p.lng).then((r) => r.json());
				const adm = ((j.localityInfo && j.localityInfo.administrative) || []).map((x) => x.name).filter(good);
				a = { place: "", street: "", area: "", locality: (adm[adm.length - 1] || j.locality || "").replace(/ taluk$/i, ""), city: j.city || "", state: j.principalSubdivision || "", pin: j.postcode || "" };
			} catch (e) { /* offline */ }
		}
		const of = (S.d && S.d.office) || {};
		const din = distTo(of, p);
		if (a && of.name && din !== null && din <= (of.radius || 200) + Math.min(p.acc || 0, 100)) a.place = of.name;
		if (a) a.acc = p.acc;
		ADDR.busy = false;
		if (a && (a.place || a.street || a.area || a.locality || a.city)) {
			S.addr = a;
			ADDR.at = { lat: p.lat, lng: p.lng, acc: p.acc };
			gpsPaint();
			if (!a.place || a.place === (a.area || "") || /complex|nagar|colony/i.test(a.place)) {
				nearbyPlace(p).then((near) => {
					if (!near || S.addr !== a) return;
					if (near.inside) a.place = near.name;
					else if (!a.place) a.place = "Near " + near.name;
					gpsPaint();
				}).catch(() => {});
			}
		}
	}
	function startGps() {
		if (!navigator.geolocation) { S.gpsErr = "This phone / browser has no GPS."; gpsPaint(); return; }
		if (S.watch !== null) return;
		S.watch = navigator.geolocation.watchPosition((p) => {
			S.pos = { lat: p.coords.latitude, lng: p.coords.longitude, acc: Math.round(p.coords.accuracy || 0), at: Date.now() };
			S.gpsErr = "";
			gpsPaint();
			geocode(false);
		}, (e) => {
			S.gpsErr = e.code === 1 ? "Location is blocked. Allow location for this app in the phone settings, then reload." : "Finding your location… (" + e.message + ")";
			gpsPaint();
		}, { enableHighAccuracy: true, maximumAge: 5000, timeout: 30000 });
	}
	function gpsState() {
		const o = (S.d && S.d.office) || {}, e = (S.d && S.d.employee) || {};
		if (S.gpsErr && !S.pos) return { cls: "bad", txt: S.gpsErr, ok: !(o.block && o.set && !e.anywhere) };
		if (!S.pos) return { cls: "", txt: "Finding your location…", ok: !(o.block && o.set && !e.anywhere) };
		const d = distTo(o, S.pos);
		if (d === null) return { cls: "ok", txt: `Location found (±${S.pos.acc} m)${o.set ? "" : " · office place not set yet"}`, ok: true, d: null };
		const inside = d <= (o.radius || 200) + Math.min(S.pos.acc, 100);
		const strict = o.block && !e.anywhere;
		if (inside) return { cls: S.pos.acc > 150 ? "warn" : "ok", txt: `Inside ${esc(o.name || "the office")} · ${km(d)} away (±${S.pos.acc} m)`, ok: true, d: d, inside: true };
		return { cls: strict ? "bad" : "warn", d: d, inside: false, ok: !strict,
			txt: strict ? `You are ${km(d)} from ${esc(o.name || "the office")}. Punch works only within ${o.radius} m.`
				: `Outside ${esc(o.name || "the office")} · ${km(d)} away. The punch will be marked “outside”.` };
	}
	function gpsPaint() {
		const g = gpsState();
		const rough = S.pos && S.pos.acc > 60 ? `<br><span style="opacity:.8">⚠ Location is rough (±${S.pos.acc} m) – the building may be wrong. On a phone, turn on GPS / “precise location”; on a computer the place is only guessed from Wi-Fi.</span>` : "";
		const at = (S.addr ? `<br><b>📍 ${esc(addrText(S.addr))}</b>` : (S.pos ? `<br><span style="opacity:.75">📍 finding street name…</span>` : "")) + rough;
		document.querySelectorAll("[data-gps]").forEach((el) => { el.innerHTML = `<span class="sbo-dot ${g.cls}"></span><span>${g.txt}${at}</span>`; });
		const sh = $("#sbo-shutter");
		if (sh && !S.shot) sh.disabled = !g.ok;
		const ring = $(".sbo-ring");
		if (ring) {
			ring.classList.toggle("off", !g.ok);
			const sub = ring.querySelector("span");
			if (sub) sub.textContent = g.ok ? "tap \u00b7 selfie + location" : (S.pos ? "come inside the office" : "waiting for location\u2026");
		}
		const rw = $("#sbo-reason");
		if (rw) rw.classList.toggle("hide", !(g.d !== null && g.d !== undefined && g.inside === false && g.ok));
	}

	// ---------------------------------------------------------------- reminders (notifications)
	function remTargets() {
		const d = S.d || {}, o = d.office || {};
		const rem = Number(o.reminder || 0);
		if (!d.employee || !rem || d.is_holiday) return [];
		const today = ymd(new Date()), out = [];
		const at = (hhmm) => { const [h, m] = hhmm.split(":").map(Number); const x = new Date(); x.setHours(h, m - rem, 0, 0); return x; };
		if (o.in_time && !(d.logs || []).length) out.push({ key: today + "-IN", when: at(o.in_time), title: "Punch IN in " + rem + " min", body: "Office starts at " + o.in_time + ". Open SBI Office and punch IN." });
		if (o.out_time && d.next === "OUT") out.push({ key: today + "-OUT", when: at(o.out_time), title: "Punch OUT in " + rem + " min", body: "Office ends at " + o.out_time + ". Punch OUT before you leave." });
		return out;
	}
	const NATIVE = window.SBIApp && typeof window.SBIApp.schedule === "function" ? window.SBIApp : null;
	function nativeSchedule() {
		// Android app: real phone alarms that ring even when the app is closed
		if (!NATIVE || !S.d || !S.d.employee || S.asEmp) return;
		const o = S.d.office || {}, rem = Number(o.reminder || 0);
		["IN-today", "OUT-today", "IN-next"].forEach((k) => { try { NATIVE.cancel(k); } catch (e) { /* ignore */ } });
		if (!rem) return;
		const now = Date.now();
		remTargets().forEach((t) => {
			if (t.when.getTime() > now) { try { NATIVE.schedule(t.key.slice(11) + "-today", String(t.when.getTime()), t.title, t.body); } catch (e) { /* ignore */ } }
		});
		if (o.in_time && !S.d.tomorrow_holiday) {
			const [h, m] = o.in_time.split(":").map(Number);
			const x = new Date(); x.setDate(x.getDate() + 1); x.setHours(h, m - rem, 0, 0);
			try { NATIVE.schedule("IN-next", String(x.getTime()), "Punch IN in " + rem + " min", "Office starts at " + o.in_time + ". Open SBI Office and punch IN."); } catch (e) { /* ignore */ }
		}
	}
	async function notify(t) {
		try { navigator.vibrate && navigator.vibrate([200, 100, 200]); } catch (e) { /* ignore */ }
		if (NATIVE) { try { NATIVE.notify(t.title, t.body); return; } catch (e) { /* fall back */ } }
		if (!("Notification" in window) || Notification.permission !== "granted") { toast(t.title + " – " + t.body, "info"); return; }
		const opt = { body: t.body, tag: "sbo-" + t.key, renotify: true, icon: (S.d && S.d.logo) || undefined, data: { url: APP } };
		try {
			const reg = swReg || (navigator.serviceWorker && await navigator.serviceWorker.getRegistration("/files/"));
			if (reg) { await reg.showNotification(t.title, opt); return; }
		} catch (e) { /* fall back */ }
		try { new Notification(t.title, opt); } catch (e) { toast(t.title + " – " + t.body, "info"); }
	}
	function remTick() {
		if (S.asEmp) return;
		const now = Date.now();
		remTargets().forEach((t) => {
			const due = t.when.getTime();
			let done = "";
			try { done = localStorage.getItem("sbo-rem-" + t.key) || ""; } catch (e) { /* private mode */ }
			if (!done && now >= due && now < due + 30 * 60000) {
				try { localStorage.setItem("sbo-rem-" + t.key, "1"); } catch (e) { /* ignore */ }
				notify(t);
			}
		});
	}
	async function askNotify() {
		if (!("Notification" in window)) { toast("This browser cannot show notifications.", "warn"); return; }
		const p = await Notification.requestPermission();
		if (p === "granted") { toast("Reminders are on. You will get a reminder before office time.", "ok"); notify({ key: "test", title: "SBI Office reminders are on", body: "You will be reminded before punch IN and punch OUT." }); }
		render();
	}

	// ---------------------------------------------------------------- screens
	function shell(inner) {
		const d = S.d || {};
		const tabs = [["punch", "Punch", ICON.home], ["month", "My month", ICON.cal]];
		if (d.is_manager) tabs.push(["team", "Team", ICON.team]);
		return `<div class="sbo-top"><div class="sbo-logo">${d.logo ? `<img src="${esc(d.logo)}" alt="">` : "⏱"}</div>
			<div class="sbo-brand"><b>SBI Office</b><span>Staff attendance</span></div>
			<div class="sbo-clock"><b id="sbo-time"></b><span id="sbo-date"></span></div></div>
			<div class="sbo-wrap">${inner}</div>
			<nav class="sbo-nav">${tabs.map((t) => `<a data-a="tab" data-t="${t[0]}" class="${S.tab === t[0] ? "on" : ""}">${t[2]}${t[1]}</a>`).join("")}</nav>`;
	}
	function picker() {
		const d = S.d;
		if (!d.is_manager) return "";
		const staff = d.staff || [];
		return `<div class="sbo-card sbo-pick"><h3>👤 Employee <span class="sbo-mut">HR / owner / Administrator</span></h3>
			<select id="sbo-as" data-a="as">${d.own_employee ? `<option value="">Me – ${esc(d.own_employee)}</option>` : `<option value="">— choose an employee —</option>`}
			${staff.map((s) => `<option value="${esc(s.name)}" ${S.asEmp === s.name ? "selected" : ""}>${esc(s.employee_name)}${s.designation ? " · " + esc(s.designation) : ""}</option>`).join("")}</select>
			${S.asEmp ? `<div class="sbo-mut" style="margin-top:6px">You are punching <b>for this employee</b>. The punch is saved as “by HR” with your name, and the office-area limit does not apply.</div>` : ""}</div>`;
	}
	function viewPunch() {
		const d = S.d, e = d.employee, o = d.office || {};
		if (!e && d.is_manager) return picker() + `<div class="sbo-card"><div class="sbo-mut">Your own login (${esc(d.user)}) is not linked to an employee, so you cannot punch for yourself.
			Choose an employee above to punch for them, or open <b>Team</b> to see everyone and change the settings.</div></div>`;
		if (!e) return `<div class="sbo-card"><h3>Your login is not linked to an employee</h3>
			<div class="sbo-mut">To punch, HR must open your <b>Employee</b> record and put your login (<b>${esc(d.user)}</b>) in the <b>User ID</b> field. Then reload this app.</div></div>`;
		const next = d.next || "IN";
		const ini = (e.employee_name || "?").split(" ").map((x) => x[0]).join("").slice(0, 2).toUpperCase();
		const logs = d.logs || [];
		const firstIn = logs.find((l) => l.log_type === "IN");
		const lastOut = logs.filter((l) => l.log_type === "OUT").pop();
		let h = picker();
		if (!NATIVE && "Notification" in window && Notification.permission === "default" && Number(o.reminder))
			h += `<div class="sbo-banner info">🔔 Get a reminder ${o.reminder} min before office time.<button class="sbo-btn sm pri" data-a="notify">Turn on</button></div>`;
		if (d.is_holiday) h += `<div class="sbo-banner info">Today is a holiday. You can still punch if you are working.</div>`;
		if (!o.set) h += `<div class="sbo-banner warn">The office place is not set yet. ${d.is_manager ? "Open Team → Office place, stand inside the office and press “Set office here”." : "Ask HR to set it."}</div>`;
		h += `<div class="sbo-card"><div class="sbo-who"><div class="sbo-av">${e.image ? `<img src="${esc(e.image)}" alt="">` : esc(ini)}</div>
			<div><div class="sbo-name">${esc(e.employee_name)}</div><div class="sbo-mut">${esc([e.designation, e.department].filter(Boolean).join(" · ") || e.name)}</div></div></div>
			<div class="sbo-shift"><div><b>${esc(o.in_time || "–")}</b><span>office starts</span></div><div><b>${esc(o.out_time || "–")}</b><span>office ends</span></div>
				<div><b>${d.hours ? d.hours.toFixed(1) + " h" : "–"}</b><span>worked today</span></div></div>
			<div class="sbo-gps" data-gps></div>
			<div class="sbo-punch"><button class="sbo-ring ${next === "OUT" ? "out" : ""}" data-a="open">${ICON.finger}<b>PUNCH ${next}</b><span>tap · selfie + location</span></button></div>
			<div class="sbo-note sbo-mut">${firstIn ? `In at <b>${esc(firstIn.t)}</b>` : "Not punched in yet"}${lastOut ? ` · Out at <b>${esc(lastOut.t)}</b>` : ""} · ${d.month || 0} day(s) this month</div></div>`;
		let appCard = !NATIVE && /android/i.test(navigator.userAgent || "") ? `<div class="sbo-banner info">📱 Install the SBI Office Android app for punch reminders.<a class="sbo-btn sm pri" href="${APK}" download>Download</a></div>` : "";
		if (IOS && !STANDALONE) appCard = `<div class="sbo-banner info">📱 <span><b>Install on iPhone:</b> open this page in <b>Safari</b>, tap <b>Share</b> (□↑) → <b>Add to Home Screen</b> → Add. SBI Office then opens like an app.</span></div>`;
		const faces = e.enrolled ? `<div class="sbo-card"><h3>Face record <span class="sbo-mut">${esc(e.sbi_face_on ? "taken " + e.sbi_face_on : "")}</span></h3>
			<div class="sbo-faces">${["front", "left", "right"].map((k) => e["sbi_face_" + k] ? `<a href="${esc(e["sbi_face_" + k])}" target="_blank"><img src="${esc(e["sbi_face_" + k])}" alt=""><i>${k}</i></a>` : "").join("")}</div>
			${d.is_manager ? `<div class="sbo-row"><button class="sbo-btn sm" data-a="resetface">Retake face photos</button></div>` : ""}</div>`
			: `<div class="sbo-banner info">📸 First punch: the app takes 3 face photos (front, left, right) for your record. It takes 20 seconds.</div>`;
		h += appCard + `<div class="sbo-card"><h3>Today</h3>${logs.length ? `<ul class="sbo-tl">${logs.map((l) => `<li><span class="sbo-tag ${l.log_type === "OUT" ? "out" : ""}">${esc(l.log_type)}</span>
			<span class="t">${esc(l.t)}</span><span class="m">${l.distance ? km(l.distance) + " from office" : ""}${l.within === 0 ? ` <span class="sbo-pill r">outside</span>` : ""}
			${l.address ? `<br>📍 ${esc(l.address)}` : ""}${l.photo ? `<br><a href="${esc(l.photo)}" target="_blank">selfie</a>` : ""}${l.latitude ? ` · <a href="https://maps.google.com/?q=${l.latitude},${l.longitude}" target="_blank">map</a>` : ""}</span></li>`).join("")}</ul>`
			: `<div class="sbo-mut">No punch yet today.</div>`}</div>`;
		h += faces;
		return h;
	}
	function viewMonth() {
		const m = S.month;
		if (!m) return `<div class="sbo-card"><div class="sbo-mut">Loading…</div></div>`;
		const days = m.days || [];
		return `<div class="sbo-card"><h3>My salary month <span class="sbo-mut">${dmy(m.from)} – ${dmy(m.to)}</span></h3>
			<div class="sbo-row" style="margin:0 0 10px"><button class="sbo-btn sm" data-a="mprev">‹ Previous</button>${m.back ? `<button class="sbo-btn sm" data-a="mnext">Next ›</button>` : ""}</div>
			<div class="sbo-sum"><div><b>${days.length}</b><span>days present</span></div><div><b>${(m.hours || 0).toFixed(1)}</b><span>hours</span></div><div><b>${m.late || 0}</b><span>late days</span></div></div>
			${days.length ? `<table class="sbo-tbl"><thead><tr><th>Date</th><th>In</th><th>Out</th><th class="r">Hours</th></tr></thead><tbody>
			${days.map((r) => `<tr><td>${dmy(r.d)}</td><td>${esc(r.first_in || "–")}${r.late ? ` <span class="sbo-pill a">late</span>` : ""}</td>
				<td>${esc(r.last_out || "–")}${r.outside ? ` <span class="sbo-pill r">outside</span>` : ""}</td><td class="r">${r.hours ? r.hours.toFixed(2) : "–"}</td></tr>`).join("")}</tbody></table>`
			: `<div class="sbo-mut">No punches in this month.</div>`}</div>`;
	}
	function viewTeam() {
		const d = S.d, o = d.office || {}, team = d.team || [];
		const inn = team.filter((t) => t.last_type === "IN").length;
		let h = `<div class="sbo-card"><h3>Team today <span class="sbo-mut">${inn} in · ${team.filter((t) => t.punches).length}/${team.length} punched</span></h3>
			<table class="sbo-tbl"><thead><tr><th>Name</th><th>In</th><th>Out</th><th>Status</th></tr></thead><tbody>
			${team.map((t) => `<tr data-a="pick" data-e="${esc(t.employee)}" style="cursor:pointer"><td><b>${esc(t.employee_name)}</b><div class="sbo-mut">${esc(t.designation || t.employee)}</div></td><td>${esc(t.first_in || "–")}</td><td>${esc(t.last_out || "–")}</td>
				<td>${!t.punches ? (t.user_id ? `<span class="sbo-pill">not punched</span>` : `<span class="sbo-pill a">no login</span>`) : t.last_type === "IN" ? `<span class="sbo-pill g">in office</span>` : `<span class="sbo-pill">left</span>`}
				${t.outside ? ` <span class="sbo-pill r">${t.outside} outside</span>` : ""}</td></tr>`).join("")}</tbody></table></div>`;
		h += `<div class="sbo-card"><h3>Office place <span class="sbo-mut">HR / owner</span></h3>
			<div class="sbo-mut">${o.set ? `${esc(o.name || "Office")} · ${Number(o.lat).toFixed(6)}, ${Number(o.lng).toFixed(6)} · allowed area ${o.radius} m ·
				<a href="https://maps.google.com/?q=${o.lat},${o.lng}" target="_blank">map</a>` : "Not set yet. Stand inside the office and press “Set office here”."}</div>
			<div class="sbo-gps" data-gps></div>
			<label>Office name</label><input id="sbo-oname" value="${esc(o.name || "")}" placeholder="e.g. Head office">
			<label>Allowed area (metres)</label><input id="sbo-orad" type="number" min="20" step="10" value="${o.radius || 200}">
			<div class="sbo-row"><button class="sbo-btn pri" data-a="setoffice">📍 Set office here</button></div>
			</div>
			<div class="sbo-card"><h3>⚙ Settings <span class="sbo-mut">HR / owner</span></h3>
			<div class="sbo-sum" style="grid-template-columns:1fr 1fr">
				<div><label style="margin:0">Office starts at</label><input id="sbo-in" type="time" value="${esc(o.in_time || "09:30")}"></div>
				<div><label style="margin:0">Office ends at</label><input id="sbo-out" type="time" value="${esc(o.out_time || "18:30")}"></div>
				<div><label style="margin:0">Late after (minutes)</label><input id="sbo-grace" type="number" min="0" max="240" value="${o.grace || 0}"></div>
				<div><label style="margin:0">Reminder before (minutes)</label><input id="sbo-rem" type="number" min="0" max="120" value="${o.reminder || 0}"></div>
				<div><label style="margin:0">Salary month starts on day</label><input id="sbo-sd" type="number" min="1" max="28" value="${d.start_day || 1}"></div>
				<div><label style="margin:0">Allowed area (metres)</label><input id="sbo-rad2" type="number" min="20" step="10" value="${o.radius || 200}"></div></div>
			<label style="display:flex;gap:8px;align-items:center;color:var(--ink);font-size:13.5px"><input type="checkbox" id="sbo-block" style="width:auto" ${o.block ? "checked" : ""}> Allow punch only inside the office area</label>
			<div class="sbo-row"><button class="sbo-btn pri" data-a="savesettings">Save settings</button></div>
			<div class="sbo-mut" style="margin-top:6px">Tap a name in “Team today” to open that employee and punch for them.</div></div>
			<div class="sbo-card"><h3>📱 Android app</h3><div class="sbo-mut">Share this link with staff. They open it on their Android phone, install, and log in once.</div>
				<div class="sbo-row"><input readonly value="${esc(location.origin + APK)}" onclick="this.select()"><a class="sbo-btn pri" href="${APK}" download>Download APK</a></div></div>`;
		return h;
	}
	function render() {
		if (!S.d) return;
		const body = S.tab === "month" ? viewMonth() : S.tab === "team" && S.d.is_manager ? viewTeam() : viewPunch();
		$("#sbo").innerHTML = shell(body);
		clock();
		gpsPaint();
	}
	function clock() {
		const n = new Date();
		const t = $("#sbo-time"), d = $("#sbo-date");
		if (t) t.textContent = n.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
		if (d) d.textContent = n.toLocaleDateString("en-IN", { weekday: "short", day: "2-digit", month: "short" });
	}

	// ---------------------------------------------------------------- camera + punch
	// ---- photo helpers: GPS stamp burnt into the picture + GPS / time written into the JPEG (EXIF)
	function exifJpeg(dataUrl, m) {
		try {
			const bin = atob(dataUrl.split(",")[1]);
			const jpg = new Uint8Array(bin.length);
			for (let i = 0; i < bin.length; i++) jpg[i] = bin.charCodeAt(i);
			const asc = (s) => { const a = []; for (const ch of String(s)) { const c = ch.charCodeAt(0); a.push(c > 31 && c < 127 ? c : 63); } a.push(0); return a; };
			const u16 = (n) => [n & 255, (n >>> 8) & 255];
			const u32 = (n) => [n & 255, (n >>> 8) & 255, (n >>> 16) & 255, (n >>> 24) & 255];
			const rat = (num, den) => u32(Math.round(num)).concat(u32(den));
			const dms = (v) => { v = Math.abs(v); const d = Math.floor(v), mm = Math.floor((v - d) * 60), ss = ((v - d) * 60 - mm) * 60; return rat(d, 1).concat(rat(mm, 1), rat(ss * 1000, 1000)); };
			const block = (entries, start) => {
				const head = u16(entries.length), data = [];
				const dataOff = start + 2 + 12 * entries.length + 4;
				entries.forEach(([tag, type, count, val]) => {
					head.push(...u16(tag), ...u16(type), ...u32(count));
					if (val.length <= 4) { const v = val.slice(); while (v.length < 4) v.push(0); head.push(...v); }
					else { head.push(...u32(dataOff + data.length)); data.push(...val); if (data.length % 2) data.push(0); }
				});
				return head.concat([0, 0, 0, 0], data);
			};
			const dt = m.when;
			const p2 = (n) => ("0" + n).slice(-2);
			const stamp = dt.getFullYear() + ":" + p2(dt.getMonth() + 1) + ":" + p2(dt.getDate()) + " " + p2(dt.getHours()) + ":" + p2(dt.getMinutes()) + ":" + p2(dt.getSeconds());
			const tz = -dt.getTimezoneOffset(), tzs = (tz >= 0 ? "+" : "-") + p2(Math.floor(Math.abs(tz) / 60)) + ":" + p2(Math.abs(tz) % 60);
			const desc = asc(m.desc || "SBI Office");
			const ifd0 = (ex, gp) => [[0x010E, 2, desc.length, desc], [0x010F, 2, 11, asc("SBI Office")], [0x0131, 2, 11, asc("SBI Office")],
				[0x0132, 2, 20, asc(stamp)], [0x8769, 4, 1, u32(ex)]].concat(m.lat !== undefined ? [[0x8825, 4, 1, u32(gp)]] : []);
			const exif = [[0x9003, 2, 20, asc(stamp)], [0x9011, 2, 7, asc(tzs)]];
			let b0 = block(ifd0(0, 0), 8);
			const exOff = 8 + b0.length;
			const bE = block(exif, exOff);
			const gpOff = exOff + bE.length;
			b0 = block(ifd0(exOff, gpOff), 8);
			let bG = [];
			if (m.lat !== undefined) {
				const gd = dt.getUTCFullYear() + ":" + p2(dt.getUTCMonth() + 1) + ":" + p2(dt.getUTCDate());
				const gps = [[0x0000, 1, 4, [2, 3, 0, 0]], [0x0001, 2, 2, asc(m.lat >= 0 ? "N" : "S")], [0x0002, 5, 3, dms(m.lat)],
					[0x0003, 2, 2, asc(m.lng >= 0 ? "E" : "W")], [0x0004, 5, 3, dms(m.lng)],
					[0x0007, 5, 3, rat(dt.getUTCHours(), 1).concat(rat(dt.getUTCMinutes(), 1), rat(dt.getUTCSeconds(), 1))],
					[0x001D, 2, 11, asc(gd)], [0x001F, 5, 1, rat((m.acc || 0) * 10, 10)]];
				bG = block(gps, gpOff);
			}
			const tiff = [0x49, 0x49, 0x2A, 0x00, 8, 0, 0, 0].concat(b0, bE, bG);
			const len = 2 + 6 + tiff.length;
			const app1 = [0xFF, 0xE1, (len >> 8) & 255, len & 255, 0x45, 0x78, 0x69, 0x66, 0, 0].concat(tiff);
			const out = new Uint8Array(jpg.length + app1.length);
			out.set(jpg.subarray(0, 2), 0); out.set(app1, 2); out.set(jpg.subarray(2), 2 + app1.length);
			let s = "";
			for (let i = 0; i < out.length; i += 0x8000) s += String.fromCharCode.apply(null, out.subarray(i, i + 0x8000));
			return "data:image/jpeg;base64," + btoa(s);
		} catch (e) { return dataUrl; }
	}
	function grab(maxW) {
		const v = $("#sbo-video");
		if (!S.stream || !v || !v.videoWidth) return null;
		const z = S.zoom > 1 ? S.zoom : 1;   // zoom out (below 1×) keeps the whole picture
		const sw = v.videoWidth / z, sh = v.videoHeight / z;
		const ccx = S.cx === null ? v.videoWidth / 2 : S.cx, ccy = S.cy === null ? v.videoHeight / 2 : S.cy;
		const sx = Math.max(0, Math.min(v.videoWidth - sw, ccx - sw / 2)), sy = Math.max(0, Math.min(v.videoHeight - sh, ccy - sh / 2));
		const w = Math.min(maxW, Math.round(sw) || maxW), h = Math.round(w * sh / sw);
		const c = document.createElement("canvas");
		c.width = w; c.height = h;
		const g = c.getContext("2d");
		g.translate(w, 0); g.scale(-1, 1); g.drawImage(v, sx, sy, sw, sh, 0, 0, w, h); g.setTransform(1, 0, 0, 1, 0, 0);
		return { c: c, g: g, w: w, h: h };
	}
	function wrapLines(g, text, maxW) {
		const words = String(text).split(" "), out = [];
		let line = "";
		words.forEach((wd) => {
			const t = line ? line + " " + wd : wd;
			if (g.measureText(t).width > maxW && line) { out.push(line); line = wd; } else line = t;
		});
		if (line) out.push(line);
		return out;
	}
	function snapPhoto() {
		const f = grab(1080);
		if (!f) return "";
		const { c, g, w, h } = f;
		const e = S.d.employee || {}, o = S.d.office || {}, p = S.pos, dd = distTo(o, p), now = new Date(), next = S.d.next || "IN";
		const base = Math.max(14, Math.round(w / 40));
		const pad = Math.round(base * 0.8);
		const when = now.toLocaleDateString("en-IN", { weekday: "short", day: "2-digit", month: "short", year: "numeric" }) + "  " +
			now.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) + "  GMT" + (-now.getTimezoneOffset() >= 0 ? "+" : "-") +
			("0" + Math.floor(Math.abs(now.getTimezoneOffset()) / 60)).slice(-2) + ":" + ("0" + Math.abs(now.getTimezoneOffset()) % 60).slice(-2);
		const tl = (S.d.logs || []).map((l) => l.log_type + " " + l.t).concat([next + " " + now.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false })]);
		const rows = [];
		g.font = "bold " + Math.round(base * 1.25) + "px Arial";
		rows.push({ t: (e.employee_name || "") + "  ·  PUNCH " + next, f: g.font, c: next === "OUT" ? "#fecaca" : "#bbf7d0" });
		g.font = "bold " + base + "px Arial";
		const A = S.addr || {};
		const ad1 = uniq([A.place, A.street]).join(", ");
		const ad2 = uniq([A.area, A.locality]).join(", ");
		const ad3 = uniq([A.city, A.state]).join(", ") + (A.pin ? " – " + A.pin : "");
		if (!S.addr) rows.push({ t: "Address not found (no internet for maps)", f: g.font, c: "#fff" });
		[ad1, ad2, ad3].forEach((ln) => { if (ln.trim()) wrapLines(g, ln, w - pad * 2).forEach((t) => rows.push({ t: t, f: g.font, c: "#fff" })); });
		g.font = base + "px Arial";
		rows.push({ t: p ? "Lat " + p.lat.toFixed(6) + "°  Long " + p.lng.toFixed(6) + "°  ±" + p.acc + " m" : "GPS not available", f: g.font, c: "#e5e7eb" });
		if (dd !== null) rows.push({ t: km(dd) + " from " + (o.name || "office") + (dd <= (o.radius || 200) + Math.min((p && p.acc) || 0, 100) ? "  (inside)" : "  (outside)"), f: g.font, c: "#e5e7eb" });
		rows.push({ t: when, f: g.font, c: "#e5e7eb" });
		wrapLines(g, "Today: " + tl.join("  →  "), w - pad * 2).forEach((t) => rows.push({ t: t, f: g.font, c: "#fde68a" }));
		const lh = Math.round(base * 1.45);
		const bh = rows.length * lh + pad * 1.6;
		g.fillStyle = "rgba(0,0,0,.62)"; g.fillRect(0, h - bh, w, bh);
		g.fillStyle = "#c8102e"; g.fillRect(0, h - bh, Math.max(6, Math.round(base * 0.35)), bh);
		let y = h - bh + pad + base;
		rows.forEach((r) => { g.font = r.f; g.fillStyle = r.c; g.fillText(r.t, pad + Math.round(base * 0.4), y); y += lh; });
		g.font = "bold " + Math.round(base * 0.9) + "px Arial"; g.fillStyle = "rgba(255,255,255,.85)";
		const tag = "SBI Office";
		g.fillText(tag, w - pad - g.measureText(tag).width, pad + base);
		const url = c.toDataURL("image/jpeg", 0.8);
		return exifJpeg(url, { when: now, lat: p ? p.lat : undefined, lng: p ? p.lng : undefined, acc: p ? p.acc : 0,
			desc: (e.employee_name || "") + " PUNCH " + next + " | " + addrText(S.addr).replace("\u2013", "-") + (p ? " | " + p.lat.toFixed(6) + "," + p.lng.toFixed(6) : "") });
	}
	function snapFace(side) {
		const f = grab(720);
		if (!f) return "";
		const { c, g, w, h } = f;
		const base = Math.max(13, Math.round(w / 42));
		g.fillStyle = "rgba(0,0,0,.55)"; g.fillRect(0, h - base * 2.2, w, base * 2.2);
		g.fillStyle = "#fff"; g.font = "bold " + base + "px Arial";
		g.fillText(((S.d.employee || {}).employee_name || "") + " · face record · " + side + " · " + new Date().toLocaleString("en-IN"), base * 0.7, h - base * 0.75);
		return c.toDataURL("image/jpeg", 0.82);
	}

	// ---- camera overlay: first time = face record (front, left, right), then the punch selfie
	const FACE_STEPS = [
		{ k: "front", t: "1 of 3 · Look straight at the camera", arrow: "◉" },
		{ k: "left", t: "2 of 3 · Turn your face a little to your LEFT", arrow: "◀" },
		{ k: "right", t: "3 of 3 · Turn your face a little to your RIGHT", arrow: "▶" },
	];
	function camMsg(t) { const m = $("#sbo-cam-msg"); if (m) m.innerHTML = t; }
	function setMode(mode) {
		S.mode = mode;
		const d = S.d, next = d.next || "IN", e = d.employee || {};
		const enroll = mode === "enroll";
		$("#sbo-cam-title").textContent = enroll ? "Face record (one time)" : "Punch " + next;
		$("#sbo-thumbs").classList.toggle("hide", !enroll);
		$("#sbo-reason-wrap").classList.toggle("hide", enroll);
		document.querySelectorAll("#sbo-cam [data-gps]").forEach((x) => x.classList.toggle("hide", enroll));
		const sh = $("#sbo-shutter");
		sh.classList.toggle("out", !enroll && next === "OUT");
		sh.classList.toggle("enroll", enroll);
		$("#sbo-save-face").classList.add("hide");
		showLive();
		if (enroll) {
			S.faces = S.faces || {};
			const step = FACE_STEPS.find((s) => !S.faces[s.k]);
			paintThumbs();
			if (step) {
				$("#sbo-arrow").textContent = step.arrow;
				$("#sbo-arrow").classList.toggle("hide", step.k === "front");
				camMsg(`<b>${esc(step.t)}</b><br>${esc(e.employee_name || "")} – we keep these 3 photos as your record. The app fits your face in the circle by itself (use <b>−</b> / <b>+</b> if needed). Then tap the button.`);
				sh.disabled = !S.stream;
			} else {
				$("#sbo-arrow").classList.add("hide");
				camMsg("<b>All 3 photos taken.</b> Tap a photo to take it again, or save.");
				sh.disabled = true;
				$("#sbo-save-face").classList.remove("hide");
			}
		} else {
			$("#sbo-arrow").classList.add("hide");
			camMsg("Look at the camera – your face is fitted into the circle automatically (use <b>−</b> / <b>+</b> if needed). Then tap the button.");
			gpsPaint();
		}
	}
	function paintThumbs() {
		$("#sbo-thumbs").innerHTML = FACE_STEPS.map((s) => `<div class="sbo-th ${S.faces[s.k] ? "ok" : ""}" data-a="refacet" data-k="${s.k}">
			${S.faces[s.k] ? `<img src="${S.faces[s.k]}" alt="">` : `<span>${s.arrow}</span>`}<i>${s.k}</i></div>`).join("");
	}
	function showLive() {
		S.shot = "";
		const im = $("#sbo-shot");
		if (im) im.classList.add("hide");
		$("#sbo-video").classList.remove("hide");
		$("#sbo-oval").classList.remove("hide");
		$("#sbo-retake").classList.add("hide");
		$("#sbo-spacer").classList.remove("hide");
		const zb = $("#sbo-zoombar");
		if (zb && S.stream) zb.classList.remove("hide");
	}
	// ---- camera zoom + auto fit: the face is found and zoomed / moved into the circle; the user can still zoom by hand
	const FACEAPI = "https://cdn.jsdelivr.net/npm/@vladmandic/face-api/dist/face-api.js";
	const FACEMODEL = "https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model";
	let faceLib = null;
	function loadFaceApi() {
		if (faceLib) return faceLib;
		faceLib = new Promise((res) => {
			const go = async () => { try { await window.faceapi.nets.tinyFaceDetector.loadFromUri(FACEMODEL); res({ kind: "faceapi" }); } catch (e) { res(null); } };
			if (window.faceapi) { go(); return; }
			const s = document.createElement("script");
			s.src = FACEAPI; s.async = true;
			s.onload = go; s.onerror = () => res(null);
			document.head.appendChild(s);
		});
		return faceLib;
	}
	async function faceLibrary() {
		if (window.FaceDetector) {
			try { return { kind: "native", fd: new window.FaceDetector({ fastMode: true, maxDetectedFaces: 1 }) }; } catch (e) { /* not on this device */ }
		}
		return loadFaceApi();
	}
	async function detectFace(v, lib) {
		if (lib.kind === "native") {
			const r = await lib.fd.detect(v);
			return r && r[0] ? { x: r[0].boundingBox.x, y: r[0].boundingBox.y, w: r[0].boundingBox.width, h: r[0].boundingBox.height } : null;
		}
		const r = await window.faceapi.detectSingleFace(v, new window.faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.4 }));
		return r ? { x: r.box.x, y: r.box.y, w: r.box.width, h: r.box.height } : null;
	}
	const ZMIN = 0.1, ZMAX = 4;
	function zoomSetup() {
		S.zoom = 1; S.cx = null; S.cy = null; S.autoFit = true; S.faceSeen = 0;
		const tr = S.stream && S.stream.getVideoTracks()[0];
		try {
			// hardware auto focus where the camera supports it
			const caps = tr && tr.getCapabilities ? tr.getCapabilities() : {};
			if (caps && caps.focusMode && caps.focusMode.indexOf("continuous") >= 0) tr.applyConstraints({ advanced: [{ focusMode: "continuous" }] }).catch(() => {});
		} catch (e) { /* ignore */ }
		const r = $("#sbo-zoom");
		if (!r) return;
		r.min = ZMIN; r.max = ZMAX; r.step = 0.05; r.value = 1;
		$("#sbo-zoombar").classList.remove("hide");
		zoomApply(1, true);
		autoFitLoop();
	}
	function viewTransform() {
		const v = $("#sbo-video"), st = $("#sbo-cam .sbo-stage"), ov = $("#sbo-oval");
		if (!v || !st) return;
		const vw = v.videoWidth || 1, vh = v.videoHeight || 1;
		const base = Math.min(st.clientWidth / vw, st.clientHeight / vh);
		const z = S.zoom || 1;
		let tx = 0, ty = 0;
		if (S.cx !== null && S.cy !== null && ov) {
			const sr = st.getBoundingClientRect(), orr = ov.getBoundingClientRect();
			const ovalDY = (orr.top + orr.height / 2) - (sr.top + sr.height / 2);
			tx = (S.cx - vw / 2) * base * z;
			ty = -(S.cy - vh / 2) * base * z + ovalDY;
		}
		v.style.transform = "translate(" + tx.toFixed(1) + "px," + ty.toFixed(1) + "px) scaleX(-1) scale(" + z + ")";
	}
	function zoomApply(z, auto) {
		if (!auto) S.autoFit = false;
		z = Math.max(ZMIN, Math.min(ZMAX, Number(z) || 1));
		S.zoom = Math.round(z * 100) / 100;
		const r = $("#sbo-zoom"), lb = $("#sbo-zoomv");
		if (r) r.value = S.zoom;
		if (lb) lb.textContent = (S.autoFit ? "Auto " : "") + (S.zoom < 1 ? S.zoom.toFixed(2).replace(/0$/, "") : S.zoom.toFixed(1)) + "×";
		document.querySelectorAll(".sbo-zp button").forEach((b) => b.classList.toggle("on", b.dataset.a === "zauto" ? !!S.autoFit : !S.autoFit && Math.abs(Number(b.dataset.z) - S.zoom) < 0.01));
		viewTransform();
	}
	function fitTo(f) {
		const v = $("#sbo-video"), st = $("#sbo-cam .sbo-stage"), ov = $("#sbo-oval");
		if (!v || !st || !ov || !v.videoWidth) return;
		const base = Math.min(st.clientWidth / v.videoWidth, st.clientHeight / v.videoHeight);
		// face box (forehead to chin) should fill about 60% of the circle height
		const want = Math.max(ZMIN, Math.min(ZMAX, 0.6 * ov.clientHeight / (f.h * base)));
		const fx = f.x + f.w / 2, fy = f.y + f.h / 2;
		const first = S.cx === null;
		const nz = first ? want : S.zoom + (want - S.zoom) * 0.5;
		S.cx = first ? fx : S.cx + (fx - S.cx) * 0.5;
		S.cy = first ? fy : S.cy + (fy - S.cy) * 0.5;
		if (first || Math.abs(nz - S.zoom) / S.zoom > 0.04) zoomApply(nz, true); else viewTransform();
	}
	async function autoFitLoop() {
		if (S.fitRun) return;
		S.fitRun = true;
		let lib = await faceLibrary();
		const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
		while (S.stream && $("#sbo-cam")) {
			const v = $("#sbo-video");
			if (lib && S.autoFit && !S.shot && v && v.videoWidth && !v.classList.contains("hide")) {
				try {
					const f = await detectFace(v, lib);
					if (f && f.h > 20) { S.faceSeen = Date.now(); fitTo(f); }
				} catch (e) {
					// the built-in detector is not available here: switch to the downloaded one
					if (lib.kind === "native") lib = await loadFaceApi(); else lib = null;
				}
			}
			await sleep(300);
		}
		S.fitRun = false;
	}
	function pinchStart(ev) {
		if (ev.touches && ev.touches.length === 2) {
			const t = ev.touches;
			S.pinch = { d: Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY), z: S.zoom || 1 };
		}
	}
	function pinchMove(ev) {
		if (!S.pinch || !ev.touches || ev.touches.length !== 2) return;
		ev.preventDefault();
		const t = ev.touches;
		const d = Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY);
		zoomApply(S.pinch.z * d / S.pinch.d);
	}
	async function openCam() {
		const d = S.d, e = d.employee || {};
		S.shot = "";
		S.faces = {};
		const ov = document.createElement("div");
		ov.className = "sbo-cam";
		ov.id = "sbo-cam";
		ov.innerHTML = `<div class="sbo-cam-top"><b id="sbo-cam-title"></b><span style="color:#ddd">${esc(e.employee_name || "")}</span><span style="margin-left:auto" id="sbo-cam-clock"></span></div>
			<div class="sbo-stage"><video id="sbo-video" playsinline autoplay muted></video><img id="sbo-shot" class="hide" alt="">
				<div class="sbo-oval" id="sbo-oval"></div><div class="sbo-arrow hide" id="sbo-arrow"></div>
				<div class="sbo-zoombar hide" id="sbo-zoombar">
					<div class="sbo-zp"><button data-a="zauto" class="on">Auto</button>${[0.1, 0.3, 0.6, 0.8, 1, 2].map((z) => `<button data-a="zset" data-z="${z}">${z}×</button>`).join("")}</div>
					<button data-a="zout" aria-label="Zoom out">−</button>
					<input type="range" id="sbo-zoom" min="1" max="4" step="0.1" value="1" aria-label="Zoom"><button data-a="zin" aria-label="Zoom in">+</button><b id="sbo-zoomv">1.0×</b></div></div>
			<div class="sbo-cam-msg" id="sbo-cam-msg"></div>
			<div class="sbo-thumbs hide" id="sbo-thumbs"></div>
			<div class="sbo-cam-low">
				<div class="sbo-cam-reason hide" id="sbo-reason-wrap"><div class="hide" id="sbo-reason"><input id="sbo-reason-in" placeholder="You are outside – reason (e.g. client visit)"></div></div>
				<div class="sbo-cam-gps" data-gps></div>
				<div class="sbo-cam-bar"><button class="sbo-btn" data-a="cancel">Cancel</button>
					<button class="sbo-shutter" id="sbo-shutter" data-a="snap" aria-label="Take photo"></button>
					<button class="sbo-btn hide" data-a="retake" id="sbo-retake">Retake</button><button class="sbo-btn pri hide" data-a="saveface" id="sbo-save-face">Save photos</button>
					<button class="sbo-btn" data-a="noop" id="sbo-spacer" style="visibility:hidden">.</button></div></div>`;
		document.body.appendChild(ov);
		$("#sbo-cam-clock").textContent = new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
		setMode(e.enrolled === 0 ? "enroll" : "punch");
		try {
			S.stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 960 } }, audio: false });
			$("#sbo-video").srcObject = S.stream;
			setMode(S.mode);
			zoomSetup();
			const st = ov.querySelector(".sbo-stage");
			st.addEventListener("touchstart", pinchStart, { passive: true });
			st.addEventListener("touchmove", pinchMove, { passive: false });
			st.addEventListener("touchend", () => { S.pinch = null; });
		} catch (err) {
			S.stream = null;
			camMsg("Camera is not allowed (" + esc(err.message || err.name) + "). Allow the camera for this app and try again.");
			$("#sbo-shutter").disabled = true;
		}
		geocode(true);
	}
	function closeCam() {
		if (S.stream) S.stream.getTracks().forEach((t) => t.stop());
		S.stream = null;
		const c = $("#sbo-cam");
		if (c) c.remove();
	}
	async function saveFaces() {
		if (S.busy) return;
		S.busy = true;
		$("#sbo-save-face").disabled = true;
		camMsg("Saving your face photos…");
		try {
			const r = await call("enroll", { photo_front: S.faces.front, photo_left: S.faces.left, photo_right: S.faces.right });
			S.d.employee = Object.assign(S.d.employee || {}, r.employee || {}, { enrolled: 1 });
			S.busy = false;
			toast("Face photos saved. Now take your punch selfie.", "ok");
			setMode("punch");
		} catch (err) {
			S.busy = false;
			$("#sbo-save-face").disabled = false;
			camMsg(esc(err.message || "Could not save. Check the internet and try again."));
		}
	}
	async function doPunch() {
		if (S.busy) return;
		if (S.mode === "enroll") {
			const step = FACE_STEPS.find((s) => !S.faces[s.k]);
			if (!step) return;
			const ph = snapFace(step.k);
			if (!ph) { toast("Camera is not ready yet. Wait a second and tap again.", "warn"); return; }
			S.faces[step.k] = ph;
			try { navigator.vibrate && navigator.vibrate(60); } catch (e) { /* ignore */ }
			setMode("enroll");
			return;
		}
		const g = gpsState();
		if (!g.ok) { toast(g.txt.replace(/<[^>]+>/g, ""), "warn"); return; }
		if (!S.shot) {
			S.shot = snapPhoto();
			if (!S.shot) { toast("Camera is not ready yet. Wait a second and tap again.", "warn"); return; }
			$("#sbo-shot").src = S.shot; $("#sbo-shot").classList.remove("hide"); $("#sbo-video").classList.add("hide"); $("#sbo-oval").classList.add("hide");
			$("#sbo-retake").classList.remove("hide"); $("#sbo-spacer").classList.add("hide");
			$("#sbo-zoombar").classList.add("hide");
			camMsg("Looks good? Tap the button again to punch.");
			return;
		}
		if (!S.pos && !window.confirm("Your location is not found yet. Punch without location?")) return;
		S.busy = true;
		const sh = $("#sbo-shutter");
		if (sh) sh.disabled = true;
		camMsg("Saving your punch…");
		try {
			const next = S.d.next || "IN";
			const r = await call("punch", { log_type: next, latitude: S.pos ? S.pos.lat : "", longitude: S.pos ? S.pos.lng : "", accuracy: S.pos ? S.pos.acc : "",
				photo: S.shot, address: addrText(S.addr), remarks: ($("#sbo-reason-in") || {}).value || "", device: (navigator.userAgent || "").slice(0, 80) });
			const p = r.punched || {};
			const shot = S.shot;
			closeCam();
			S.d = Object.assign(S.d, r);
			S.busy = false;
			render();
			nativeSchedule();
			const ok = document.createElement("div");
			ok.className = "sbo-done " + (p.log_type === "OUT" ? "out" : "");
			ok.innerHTML = `${shot ? `<img src="${shot}" alt="">` : `<div class="tick">✓</div>`}<b>Punched ${esc(p.log_type)} at ${esc(p.time)}</b>
				<div>${p.late ? "Late by " + p.late + " min" : p.early ? "Leaving " + p.early + " min early" : p.log_type === "IN" ? "Have a good day!" : "Thank you – see you tomorrow!"}</div>
				${S.addr ? `<div>📍 ${esc(addrText(S.addr))}</div>` : ""}
				${p.within === 0 ? `<div>Marked outside the office (${km(p.distance)} away)</div>` : p.distance ? `<div>${km(p.distance)} from office</div>` : ""}`;
			document.body.appendChild(ok);
			try { navigator.vibrate && navigator.vibrate(120); } catch (e) { /* ignore */ }
			setTimeout(() => ok.remove(), 3200);
			ok.addEventListener("click", () => ok.remove());
		} catch (e) {
			S.busy = false;
			if (sh) sh.disabled = false;
			camMsg(esc(e.message || "Could not save. Check the internet and try again."));
		}
	}
	async function loadMonth() {
		S.month = null;
		render();
		try { const r = await call("month", { back: S.back }); S.month = r.month_view || { days: [] }; } catch (e) { S.month = { days: [] }; toast(e.message); }
		render();
	}
	async function load() {
		S.d = await call("status");
		if (!S.d.employee && S.d.is_manager && S.tab === "punch" && !S.chosen) S.tab = "team";
		render();
		remTick();
		nativeSchedule();
	}

	document.addEventListener("click", async (ev) => {
		const el = ev.target.closest("[data-a]");
		if (!el || !el.closest(".sbo, .sbo-cam")) return;
		const a = el.dataset.a;
		if (a === "tab") { S.tab = el.dataset.t; if (S.tab === "month") loadMonth(); else render(); }
		else if (a === "open") {
			const g = gpsState();
			if (!g.ok) { toast(g.txt.replace(/<[^>]+>/g, ""), "warn"); return; }
			openCam();
		}
		else if (a === "cancel") closeCam();
		else if (a === "snap") doPunch();
		else if (a === "retake") { showLive(); camMsg("Keep your face inside the circle and tap the button."); gpsPaint(); }
		else if (a === "refacet") { if (S.faces) { delete S.faces[el.dataset.k]; setMode("enroll"); } }
		else if (a === "saveface") saveFaces();
		else if (a === "zset") { S.cx = null; S.cy = null; zoomApply(Number(el.dataset.z)); }
		else if (a === "zauto") { S.autoFit = true; zoomApply(S.zoom, true); }
		else if (a === "zin") zoomApply((S.zoom || 1) + ((S.zoom || 1) < 1 ? 0.1 : 0.25));
		else if (a === "zout") zoomApply((S.zoom || 1) - ((S.zoom || 1) <= 1 ? 0.1 : 0.25));
		else if (a === "resetface") {
			if (!window.confirm("Clear this employee's face photos? They will take new ones at the next punch.")) return;
			try { const r = await call("reset_face"); S.d.employee = Object.assign(S.d.employee || {}, r.employee || {}); render(); toast("Face photos cleared.", "ok"); } catch (e) { toast(e.message); }
		}
		else if (a === "notify") askNotify();
		else if (a === "pick") { S.asEmp = el.dataset.e; S.chosen = 1; S.tab = "punch"; load().catch((e) => toast(e.message)); }
		else if (a === "savesettings") {
			try {
				const r = await call("save_settings", { in_time: $("#sbo-in").value, out_time: $("#sbo-out").value, grace: $("#sbo-grace").value, reminder: $("#sbo-rem").value,
					start_day: $("#sbo-sd").value, radius: $("#sbo-rad2").value, block: $("#sbo-block").checked ? 1 : 0, office_name: $("#sbo-oname").value });
				S.d = Object.assign(S.d, r);
				render();
				toast("Settings saved.", "ok");
			} catch (e) { toast(e.message); }
		}
		else if (a === "mprev") { S.back += 1; loadMonth(); }
		else if (a === "mnext") { S.back = Math.max(0, S.back - 1); loadMonth(); }
		else if (a === "setoffice") {
			if (!S.pos) { toast("Your location is not found yet. Wait a few seconds and try again."); return; }
			if (!window.confirm("Set the office to where you are standing now (±" + S.pos.acc + " m)?")) return;
			try {
				const r = await call("set_office", { latitude: S.pos.lat, longitude: S.pos.lng, radius: $("#sbo-orad").value, office_name: $("#sbo-oname").value });
				S.d = Object.assign(S.d, r);
				render();
				toast("Office place saved.", "ok");
			} catch (e) { toast(e.message); }
		}
	});
	document.addEventListener("input", (ev) => { if (ev.target && ev.target.id === "sbo-zoom") zoomApply(ev.target.value); });
	document.addEventListener("change", (ev) => {
		if (ev.target && ev.target.id === "sbo-as") { S.asEmp = ev.target.value; S.chosen = 1; S.month = null; load().catch((e) => toast(e.message)); }
	});
	window.addEventListener("resize", () => { if ($("#sbo-cam")) viewTransform(); });
	document.addEventListener("visibilitychange", () => { if (!document.hidden && S.d && !$("#sbo-cam")) load().catch(() => {}); });

	function start() {
		setInterval(clock, 10000);
		setInterval(remTick, 30000);
		startGps();
		load().catch((e) => { if (e.message !== "login" && $("#sbo")) $("#sbo").innerHTML = `<div class="sbo-wrap"><div class="sbo-card"><div class="sbo-banner warn">${esc(e.message || "Could not load.")} Check the internet and reload.</div></div></div>`; });
	}
	// wait for the page to finish (the login token is written after this script)
	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();'''
ICON_180 = (
    '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'
)
ICON_192 = (
    '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'
)
ICON_512 = (
    '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'
)
wp_name = frappe.db.get_value("Web Page", {"route": "sbi_office"}, "name")
if not wp_name:
    frappe.throw("SBI Office page not found. Run the full lite_erp_console.py installer once first.")
wp = frappe.get_doc("Web Page", wp_name)
wp.main_section_html = OFFICE_HTML
wp.css = OFFICE_CSS
wp.insert_style = 1
wp.javascript = OFFICE_JS
wp.save(ignore_permissions=True)
log("app page updated: /sbi_office")
for pair in [["sbi_office_icon_180.png", ICON_180], ["sbi_office_icon_192.png", ICON_192], ["sbi_office_icon_512.png", ICON_512]]:
    if frappe.get_all("File", filters={"file_url": "/files/" + pair[0]}, pluck="name"):
        log("icon kept: /files/" + pair[0])
        continue
    idoc = frappe.get_doc({"doctype": "File", "file_name": pair[0], "is_private": 0, "content": pair[1], "decode": True})
    idoc.flags.ignore_permissions = True
    idoc.insert(ignore_permissions=True)
    log("icon saved: " + idoc.file_url)
MANIFEST = '{"name": "SBI Office - Staff Attendance", "short_name": "SBI Office", "id": "/sbi_office", "start_url": "/sbi_office", "scope": "/sbi_office", ' + \
    '"display": "standalone", "orientation": "portrait", "background_color": "#f3f4f6", "theme_color": "#c8102e", ' + \
    '"description": "Punch IN / OUT with selfie and GPS", "icons": [{"src": "/files/sbi_office_icon_192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"}, ' + \
    '{"src": "/files/sbi_office_icon_512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}]}'
if not frappe.get_all("File", filters={"file_url": "/files/sbi_office_manifest_v2.json"}, pluck="name"):
    mdoc = frappe.get_doc({"doctype": "File", "file_name": "sbi_office_manifest_v2.json", "is_private": 0, "content": MANIFEST})
    mdoc.flags.ignore_permissions = True
    mdoc.insert(ignore_permissions=True)
    log("file saved: " + mdoc.file_url)
frappe.db.commit()
log("DONE. Reload SBI Office (Ctrl+Shift+R). On iPhone: Safari -> Share -> Add to Home Screen.")
