// SBI Lite ERP - single page: fixed top menu, drill-down screens, ERPNext forms open inside the page.
// root_element is the block's shadow root (given by Frappe).
const R = root_element;
const q = (s) => R.querySelector(s);
const API = "sbi_lite_erp";
// v16 desk lives at /desk (older sites use /app)
const BASE = window.location.pathname.indexOf("/app") === 0 ? "/app" : "/desk";

// ------------------------------------------------------------------ helpers
const esc = (v) => frappe.utils.escape_html(v === null || v === undefined ? "" : String(v));
const money = (v) => {
	const n = Number(v || 0);
	return (n < 0 ? "-" : "") + "₹ " + Math.abs(Math.round(n)).toLocaleString("en-IN");
};
const num = (v) => {
	const n = Math.round(Number(v || 0) * 1000) / 1000;
	return n.toLocaleString("en-IN");
};
const dt = (d) => (d ? frappe.datetime.str_to_user(String(d).slice(0, 10)) : "");
const slug = (doctype) => doctype.toLowerCase().replace(/ /g, "-");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const call = (action, args) =>
	frappe.call({ method: API, args: Object.assign({ action: action, company: S.company }, args || {}) })
		.then((r) => (r && r.message) || {});
const statusPill = (s, docstatus) => {
	if (docstatus === 0) return `<span class="pill orange">Draft</span>`;
	const t = String(s || "");
	const cls = /paid|completed|fully|submitted/i.test(t) ? "green" : /overdue|unpaid|cancel/i.test(t) ? "red" : /partly|partial|draft/i.test(t) ? "orange" : "";
	return `<span class="pill ${cls}">${esc(t || "-")}</span>`;
};
async function waitFor(fn, ms) {
	const end = Date.now() + (ms || 15000);
	while (Date.now() < end) {
		let v = null;
		try { v = fn(); } catch (e) { v = null; }
		if (v) return v;
		await sleep(150);
	}
	throw new Error("Timed out");
}

// ------------------------------------------------------------------ icons (simple stroke icons)
const ICON_PATHS = {
	home: "M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
	folder: "M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
	receipt: "M6 2h12v20l-3-2-3 2-3-2-3 2zM9 7h6M9 11h6M9 15h4",
	cart: "M3 4h2l2.5 11h11L21 7H7M9 20h.01M18 20h.01",
	wallet: "M20 7V5a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H5a2 2 0 0 1-2-2V6M16 13h.01",
	bank: "M3 10l9-6 9 6M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 21h18",
	map: "M12 21s-7-6.5-7-12a7 7 0 0 1 14 0c0 5.5-7 12-7 12zM12 11a2 2 0 1 0 0-4 2 2 0 0 0 0 4z",
	users: "M16 20v-1a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v1M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM22 20v-1a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8",
	percent: "M19 5L5 19M7 9a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM17 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4z",
	upload: "M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3",
	download: "M12 4v12M7 11l5 5 5-5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3",
	info: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 16v-4M12 8h.01",
	trend: "M3 17l6-6 4 4 8-8M15 7h6v6",
	inbox: "M22 12h-6l-2 3h-4l-2-3H2M5.5 5h13l3.5 7v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6z",
	outbox: "M12 3v10M8 7l4-4 4 4M2 13h6l2 3h4l2-3h6v5a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2z",
	clock: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 6v6l4 2",
	check: "M20 6L9 17l-5-5",
	alert: "M12 9v4M12 17h.01M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
	calendar: "M3 6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM3 10h18M8 2v4M16 2v4",
	plus: "M12 5v14M5 12h14",
	search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3",
	user: "M20 21v-1a5 5 0 0 0-5-5H9a5 5 0 0 0-5 5v1M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
};
const ICON = (n, cls) => `<svg class="ic ${cls || ""}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${ICON_PATHS[n] || ICON_PATHS.info}"/></svg>`;
const MENU_ICON = { me: "user", home: "home", projects: "folder", sales: "receipt", purchase: "cart", cash: "wallet", bank: "bank", site: "map", hr: "users", gst: "percent" };

// ------------------------------------------------------------------ small charts (plain SVG, no library)
function barChart(rows, keys, colors, names) {
	const W = 640, H = 230, L = 64, B = 30, T = 14;
	const realMax = Math.max(0, ...rows.map((r) => Math.max(...keys.map((k) => Number(r[k] || 0)))));
	if (!realMax) return `<div class="chart-empty">${ICON("trend")}<span>No sales or purchase bills in the last 6 months yet.<br>The chart fills in as bills are submitted.</span></div>`;
	const max = realMax;
	const step = Math.pow(10, Math.floor(Math.log10(max)));
	const top = Math.ceil(max / step) * step;
	const gw = (W - L - 10) / rows.length, bw = Math.min(26, (gw - 16) / keys.length);
	const short = (v) => v >= 1e7 ? (v / 1e7).toFixed(v >= 1e8 ? 0 : 1) + " Cr" : v >= 1e5 ? (v / 1e5).toFixed(v >= 1e6 ? 0 : 1) + " L" : v >= 1e3 ? Math.round(v / 1e3) + " K" : String(Math.round(v));
	let s = `<svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">`;
	for (let i = 0; i <= 4; i++) {
		const y = T + (H - T - B) * (1 - i / 4);
		s += `<line x1="${L}" x2="${W - 6}" y1="${y}" y2="${y}" class="gl"/><text x="${L - 8}" y="${y + 4}" text-anchor="end" class="ax">${short(top * i / 4)}</text>`;
	}
	rows.forEach((r, i) => {
		const x0 = L + i * gw + (gw - bw * keys.length - 4 * (keys.length - 1)) / 2;
		keys.forEach((k, j) => {
			const v = Number(r[k] || 0), h = (H - T - B) * v / top;
			s += `<rect x="${x0 + j * (bw + 4)}" y="${H - B - h}" width="${bw}" height="${Math.max(h, v ? 2 : 0)}" rx="3" fill="${colors[j]}"><title>${names[j]} ${money(v)}</title></rect>`;
		});
		s += `<text x="${L + i * gw + gw / 2}" y="${H - 9}" text-anchor="middle" class="ax">${moment(r.month + "-01").format("MMM")}</text>`;
	});
	s += `</svg><div class="legend">${names.map((n, j) => `<span><i style="background:${colors[j]}"></i>${n}</span>`).join("")}</div>`;
	return s;
}

const AGE = [["not_due", "Not yet due", "#16a34a"], ["d30", "1–30 days late", "#eab308"], ["d60", "31–60", "#f97316"], ["d90", "61–90", "#ef4444"], ["d90p", "Over 90", "#991b1b"]];
function ageBar(label, a, go) {
	const tot = AGE.reduce((s, x) => s + Number(a[x[0]] || 0), 0);
	let h = `<div class="age" ${go ? `data-go="${go}"` : ""}><div class="age-h"><b>${label}</b><span>${money(tot)}</span></div><div class="age-bar">`;
	if (!tot) h += `<div class="age-empty">nothing outstanding</div>`;
	AGE.forEach((x) => { const v = Number(a[x[0]] || 0); if (v > 0) h += `<div style="width:${Math.max(2, v * 100 / tot)}%;background:${x[2]}" title="${x[1]}: ${money(v)}"></div>`; });
	h += `</div><div class="age-l">${AGE.map((x) => Number(a[x[0]] || 0) > 0 ? `<span><i style="background:${x[2]}"></i>${x[1]} <b>${money(a[x[0]])}</b></span>` : "").join("")}</div></div>`;
	return h;
}
const progress = (part, whole, cls) => {
	const p = whole > 0 ? Math.max(0, Math.min(100, part * 100 / whole)) : 0;
	return `<div class="prog ${cls || ""}"><div style="width:${p.toFixed(1)}%"></div></div>`;
};

const S = { companies: [], projects: [], company: "", period: "fy", from: "", to: "", includeBank: false, crumbs: [], menu: "" };

// ------------------------------------------------------------------ menu
const MENUS = [
	{ id: "me", label: "My work", items: [
		["me", "My attendance", "This month: punches, hours, leave"],
		["punch", "Punch IN / OUT", "SBI Office – GPS + selfie"],
		["me-att", "Attendance request", "Forgot punch, on duty, work from home…"],
		["me-leave", "Leave request", "Apply leave, see leave left"],
		["me-profile", "My details", "Phone, address, bank, photo – HR approves"],
		["me-slips", "My salary slips", ""],
		["me-pw", "Change password", ""],
	] },
	{ id: "projects", label: "Projects", items: [
		["projects", "All projects", "Money in and out for each project"],
		["new:Project", "New project", ""],
		["boq", "Project BOQ", "Project \u2192 stage \u2192 type or upload the BOQ"],
		["list:Project BOQ", "All BOQ records", ""],
	] },
	{ id: "sales", label: "Sales", items: [
		["sales", "Bill a milestone", "Project \u2192 order \u2192 milestone (MS lines)"],
		["sales-nonms", "Non-MS bill", "Lines not in any milestone (MS = No)"],
		["so-new", "New sales order", "Sl, description, area, unit, cost, MS"],
		["list:Sales Order", "All sales orders", ""],
		["sales-direct", "Direct invoice", "Bill without a sales order"],
		["list:Sales Invoice", "All sales invoices", ""],
		["receive", "Receive payment", ""],
	] },
	{ id: "purchase", label: "Purchase", items: [
		["po-bill", "Bill a milestone", "Project \u2192 purchase order \u2192 milestone"],
		["po-nonms", "Non-MS bill", "Purchase order lines not in milestones"],
		["po-new", "New purchase order", "Sl, description, area, unit, cost, MS"],
		["list:Purchase Order", "All purchase orders", ""],
		["purchase", "Purchase from BOQ", "Project \u2192 stage \u2192 BOQ items not yet bought"],
		["purchase-direct", "Direct purchase bill", "Project \u2192 stage \u2192 blank bill"],
		["list:Purchase Invoice", "All purchase invoices", ""],
		["pay", "Pay supplier", ""],
	] },
	{ id: "cash", label: "Cash Flow", items: [
		["cash-give", "Give cash to site", ""],
		["cash-expense", "Site expense", ""],
		["cash-tally", "Import from Tally", "Tally cash payments → site"],
		["page:cash-flow", "Owner dashboard", "Charts and reports"],
	] },
	{ id: "bank", label: "Bank", items: [
		["bank", "Daily bank check", "Match each entry to a GST invoice, or remark it"],
		["bank-upload", "Upload bank statement", "Excel or CSV from the bank, every day"],
		["bank-accounts", "Bank accounts", "Last statement and what is left to check"],
		["new:Bank Account", "Add bank account", ""],
		["bank-noinv", "Entries without invoice", "Reasons and remarks given"],
		["route:bank-reconciliation-tool", "ERPNext reconciliation tool", "For the accounts team"],
	] },
	{ id: "site", label: "Site Summary", items: [
		["sites", "All sites", "Billed, received, spent, margin"],
		["cash-position", "Cash with each site", ""],
	] },
	{ id: "hr", label: "HR", items: [
		["hr-dash", "HR dashboard", "Today's attendance; tap a person for the month"],
		["hr-emps", "Add / edit employee", "ID No., photo, login and allowed areas"],
		["hr-req", "Requests to approve", "Attendance, leave and detail changes"],
		["hr", "Attendance", "Day, salary month or custom dates"],
		["report:Monthly Attendance Sheet", "Attendance report", "Month sheet for all staff"],
		["letter:SBI Appointment Order", "Appointment order", "Print for an employee"],
		["letter:SBI Relieving Order", "Relieving order", "Print for an employee who leaves"],
		["list:Appointment Letter", "Appointment letters (HRMS)", ""],
		["list:Salary Structure Assignment", "Payroll details", "Salary of each employee"],
		["list:Salary Structure", "Salary structures", ""],
		["ext:/sbi_office", "SBI Office – staff punch app", "Opens the punch app (GPS + selfie)"],
		["hr-settings", "Salary month & office settings", "Month start day, office time, GPS area, reminders"],
		["list:Employee Checkin", "Office punches", "Every office punch"],
		["list:Labour", "Labour register", "Site labour, wages, face enrolment"],
		["list:Labour Attendance Log", "Labour punches", "Every punch from the site app"],
		["list:Employee", "Employees", ""],
		["list:Attendance", "Staff attendance", ""],
		["list:Leave Application", "Leave applications", ""],
		["list:Expense Claim", "Expense claims", ""],
		["list:Employee Advance", "Employee advances", ""],
		["new:Payroll Entry", "Run payroll", ""],
		["list:Salary Slip", "Salary slips", ""],
		["report:Salary Register", "Salary register", ""],
		["list:Leave Allocation", "Leave allocation", "Leave given to each employee"],
		["list:Holiday List", "Holidays", ""],
	] },
	{ id: "gst", label: "GST", items: [
		["gst", "GST to pay", "Output, input credit, paid, balance"],
		["report:Sales Register", "Sales register", ""],
		["report:Purchase Register", "Purchase register", ""],
		["list:e-Waybill Log", "e-Way bills", ""],
		["route:gst-india", "GST returns", "India Compliance (GSTR-1, 3B)"],
	] },
];

const NO_COMPANY = ["Project BOQ", "e-Waybill Log", "Labour", "Labour Attendance Log"];

function drawMenu() {
	q("#menu").innerHTML = MENUS.map((m) => `
		<div class="m ${S.menu === m.id ? "active" : ""}" data-menu="${m.id}">
			<button class="m-btn" data-go="${m.items[0][0]}" data-m="${m.id}">${ICON(MENU_ICON[m.id] || "info", "mi")}<span>${esc(m.label)}</span>${m.items.length > 1 ? ` <span class="car">\u25bc</span>` : ""}</button>
			${m.items.length > 1 ? `<div class="m-sub">${m.items.map((i) => `<a data-go="${esc(i[0])}" data-m="${m.id}">${esc(i[1])}${i[2] ? `<span class="d">${esc(i[2])}</span>` : ""}</a>`).join("")}
				<a class="m-help" data-act="help-drawer" data-h="${m.id}">${ICON("info")} How to use ${esc(m.label)}</a></div>` : ""}
		</div>`).join("");
}

function setMenu(id) {
	S.menu = id;
	R.querySelectorAll(".m").forEach((el) => el.classList.toggle("active", el.dataset.menu === id));
	const hb = q("#helpbtn");
	if (hb) hb.classList.toggle("on", id === "help");
	const brand = q(".lx-brand span");
	if (brand) brand.classList.toggle("on", id === "home");
	R.querySelectorAll(".m.open").forEach((el) => el.classList.remove("open"));
}

// crumbs: [[label, fn|null], ...]; right: extra html on the right
function crumbs(list, right) {
	S.crumbs = list;
	q("#crumbs").innerHTML = list.map((c, i) => (i ? `<span class="sep">›</span>` : "") +
		(c[1] && i < list.length - 1 ? `<a data-crumb="${i}">${esc(c[0])}</a>` : `<b>${esc(c[0])}</b>`)).join("") +
		`<span class="right">${right || ""}${S.menu !== "help" ? `<a class="hpill" data-act="help-drawer">${ICON("info")} How this works</a>` : ""}</span>`;
}

function showView(html) {
	q("#framewrap").classList.add("hide");
	q("#view").classList.remove("hide");
	if (html !== undefined) q("#view").innerHTML = html;
	const h2 = q("#view h2.t");
	if (h2 && !h2.querySelector("svg") && !h2.closest(".emp-head")) h2.insertAdjacentHTML("afterbegin", `<span class="ti">${ICON(MENU_ICON[S.menu] || "info")}</span>`);
	q("#view").scrollTop = 0;
}
const loading = () => showView(`<div class="skel"><div class="sk sk-t"></div><div class="sk sk-s"></div>
	<div class="sk-row">${"<div class='sk sk-c'></div>".repeat(4)}</div><div class="sk sk-b"></div><div class="sk sk-b short"></div></div>`);

// ------------------------------------------------------------------ embedded ERPNext (forms, lists, reports)
const FRAME_CSS = `
	header.navbar, .navbar.navbar-expand, .body-sidebar-container, .body-sidebar, .layout-side-section,
	.desk-sidebar, .sidebar-toggle-btn, .page-head .sidebar-toggle-btn { display: none !important; }
	.page-head { top: 0 !important; }
	body { padding-top: 0 !important; }
	.main-section, .page-container, .layout-main-section-wrapper { margin-left: 0 !important; }
	.page-body, .container.page-body { max-width: 100% !important; width: 100% !important; }`;

function frameStyle() {
	try {
		const d = q("#frame").contentDocument;
		if (d && d.head && !d.getElementById("lx-frame-css")) {
			const st = d.createElement("style");
			st.id = "lx-frame-css";
			st.textContent = FRAME_CSS;
			d.head.appendChild(st);
		}
	} catch (e) { /* not same origin yet */ }
}

function frameReady() {
	try {
		const w = q("#frame").contentWindow;
		if (w && w.frappe && w.frappe.set_route && w.frappe.model && w.frappe.model.get_new_doc &&
			w.frappe.boot && w.frappe.boot.user && w.document.readyState === "complete") {
			frameStyle();
			return w;
		}
	} catch (e) { /* loading */ }
	return null;
}

function frameWin() {
	const w = frameReady();
	if (w) return Promise.resolve(w);
	const f = q("#frame");
	if (!f.getAttribute("src")) f.setAttribute("src", BASE + "/sales-invoice");
	return waitFor(frameReady, 40000).then(async (w2) => { await sleep(400); return w2; });
}

function showFrame() {
	q("#view").classList.add("hide");
	q("#framewrap").classList.remove("hide");
}

function openTabLink() {
	return `<a data-act="newtab" title="Open the same page in a new browser tab">Open in new tab ↗</a>`;
}

// go to a desk route inside the page: args for frappe.set_route, url for a cold start
// args are plain route parts ("List", "Project BOQ"); opts become list / report filters
async function frameGo(args, url, opts) {
	showFrame();
	const w = frameReady();
	const has = opts && Object.keys(opts).length;
	if (w) {
		w.frappe.route_options = has ? Object.assign({}, opts) : null;
		w.frappe.set_route.apply(w.frappe, args);
		return w;
	}
	const qs = has ? "?" + Object.keys(opts).map((k) => encodeURIComponent(k) + "=" + encodeURIComponent(opts[k])).join("&") : "";
	q("#frame").setAttribute("src", url + qs);
	return frameWin();
}

function frameForm(doctype, name, back) {
	crumbs((back || []).concat([[doctype + " " + name, null]]), openTabLink());
	return frameGo(["Form", doctype, name], BASE + "/" + slug(doctype) + "/" + encodeURIComponent(name));
}

function frameList(doctype, filters, label) {
	crumbs([[label || doctype, null]], openTabLink());
	return frameGo(["List", doctype], BASE + "/" + slug(doctype), filters || {});
}

// new form inside the page, values set through the form so ERPNext's own triggers run
async function frameNew(doctype, values, after, back) {
	crumbs((back || []).concat([["New " + doctype, null]]), openTabLink());
	showFrame();
	const fz = frappe.dom.freeze(__("Opening {0}…", [__(doctype)]));
	try {
		const w = await frameWin();
		await new Promise((res) => w.frappe.model.with_doctype(doctype, res));
		const d = w.frappe.model.get_new_doc(doctype);
		w.frappe.set_route("Form", doctype, d.name);
		const frm = await waitFor(() => (w.cur_frm && w.cur_frm.doctype === doctype && w.cur_frm.docname === d.name ? w.cur_frm : null), 20000);
		await sleep(300);
		for (const k of Object.keys(values || {})) {
			if (values[k] === undefined || values[k] === null || values[k] === "") continue;
			if (!frm.fields_dict[k]) continue;
			await frm.set_value(k, values[k]);
		}
		if (after) await after(frm, w);
		return frm;
	} catch (e) {
		frappe.msgprint(__("Could not open the form inside the page. Please try again."));
		throw e;
	} finally {
		frappe.dom.unfreeze();
	}
}

// ------------------------------------------------------------------ project picker
function projectsForCompany() {
	return S.projects.filter((p) => !S.company || !p.company || p.company === S.company);
}
function pLabel(p) {
	return p.project_name && p.project_name !== p.name ? p.project_name : p.name;
}
function findProject(name) {
	return S.projects.find((p) => p.name === name) || { name: name, project_name: name };
}

function pickProject(title, sub, back, next) {
	crumbs(back.concat([["Pick a project", null]]));
	const list = projectsForCompany().slice().sort((a, b) => (a.status === "Open" ? 0 : 1) - (b.status === "Open" ? 0 : 1));
	showView(`<h2 class="t">${esc(title)}</h2><div class="sub">${esc(sub)}</div>
		<input class="search" id="psearch" placeholder="Search project or customer…" autocomplete="off">
		<div class="cards" id="pcards">${list.map((p) => `
			<div class="card ${p.status !== "Open" ? "done" : ""}" data-pick="${esc(p.name)}" data-s="${esc((p.name + " " + (p.project_name || "") + " " + (p.customer || "")).toLowerCase())}">
				<div class="n">${esc(pLabel(p))}</div>
				<div class="c">${esc(p.name)}${p.customer ? " · " + esc(p.customer) : ""}</div>
				${p.status !== "Open" ? `<div class="c"><span class="pill">${esc(p.status)}</span></div>` : ""}
			</div>`).join("") || `<div class="hint">No projects for this company.</div>`}</div>`);
	S.onPick = next;
	const s = q("#psearch");
	s.focus();
	s.addEventListener("input", () => {
		const t = s.value.toLowerCase().trim();
		R.querySelectorAll("#pcards .card").forEach((c) => c.classList.toggle("hide", !!t && c.dataset.s.indexOf(t) < 0));
	});
}

// ------------------------------------------------------------------ router
function go(key, menuId) {
	if (S.scope !== "all" && S.scope && key === "home") { key = S.homeKey || "me"; menuId = S.homeMenu || "me"; }
	helpClose();
	if (menuId) setMenu(menuId);
	const [kind, arg] = key.indexOf(":") > 0 ? [key.slice(0, key.indexOf(":")), key.slice(key.indexOf(":") + 1)] : [key, ""];
	if (kind === "ext") { window.open(arg, "_blank"); return; }
	if (kind === "letter") return pickEmployee(arg.replace("SBI ", ""), (emp) => openLetter(arg, emp));
	if (kind === "new") return frameNew(arg, { company: S.company });
	if (kind === "list") return frameList(arg, S.company && NO_COMPANY.indexOf(arg) < 0 ? { company: S.company } : {}, arg);
	if (kind === "report") {
		crumbs([[arg, null]], openTabLink());
		return frameGo(["query-report", arg], BASE + "/query-report/" + encodeURIComponent(arg), S.company ? { company: S.company } : {});
	}
	if (kind === "page" || kind === "route") {
		let lbl = arg;
		MENUS.forEach((mm) => mm.items.forEach((it) => { if (it[0] === key) lbl = it[1]; }));
		crumbs([[lbl, null]], openTabLink());
		return frameGo([arg], BASE + "/" + arg);
	}
	const V = {
		home: viewHome,
		help: () => viewHelp(),
		"hr-settings": () => viewHrSettings(),
		me: () => { S.mBack = 0; return viewMe(); },
		punch: () => { window.location.href = "/sbi_office"; },
		"me-att": viewMeAtt,
		"me-leave": viewMeLeave,
		"me-profile": viewMeProfile,
		"me-slips": viewMeSlips,
		"me-pw": () => viewChangePw(false),
		"hr-dash": viewHrDash,
		"hr-emps": viewHrDash,
		"hr-req": () => viewReqs(),
		boq: () => pickProject("Project BOQ", "Pick the project for the BOQ.", [["Project BOQ", () => go("boq", "projects")]], (p) => viewBoqStages(p)),
		bank: () => bankGo("check"),
		"bank-upload": () => bankGo("upload"),
		"bank-accounts": () => viewBankAccounts("overview"),
		"bank-noinv": viewBankNoInv,
		hr: () => viewHr(),
		projects: viewProjects,
		sites: viewSites,
		"cash-position": viewCashPosition,
		gst: viewGst,
		"cash-tally": viewTally,
		sales: () => pickProject("Bill a milestone", "Pick the project to bill.", [["Sales", () => go("sales", "sales")]], (p) => viewOrders(p, "sales", "ms")),
		"sales-nonms": () => pickProject("Non-MS bill", "Pick the project.", [["Sales", () => go("sales-nonms", "sales")]], (p) => viewOrders(p, "sales", "nonms")),
		"so-new": () => pickProject("New sales order", "Pick the project for the sales order.", [["Sales", () => go("sales", "sales")]], (p) => viewOrderForm(p, "sales")),
		"po-bill": () => pickProject("Bill a milestone (purchase)", "Pick the project.", [["Purchase", () => go("po-bill", "purchase")]], (p) => viewOrders(p, "purchase", "ms")),
		"po-nonms": () => pickProject("Non-MS purchase bill", "Pick the project.", [["Purchase", () => go("po-nonms", "purchase")]], (p) => viewOrders(p, "purchase", "nonms")),
		"po-new": () => pickProject("New purchase order", "Pick the project for the purchase order.", [["Purchase", () => go("po-bill", "purchase")]], (p) => viewOrderForm(p, "purchase")),
		"sales-direct": () => pickProject("Direct invoice", "Pick the project. The invoice opens with the project filled in.", [["Sales", () => go("sales", "sales")]],
			(p) => directSales(p)),
		receive: () => frameNew("Payment Entry", { payment_type: "Receive", company: S.company }, null, [["Sales", () => go("sales", "sales")]]),
		purchase: () => pickProject("Purchase Invoice", "Pick the project you are buying for.", [["Purchase", () => go("purchase", "purchase")]], (p) => viewStages(p, false)),
		"purchase-direct": () => pickProject("Direct purchase bill", "Pick the project, then the stage.", [["Purchase", () => go("purchase", "purchase")]], (p) => viewStages(p, true)),
		pay: () => frameNew("Payment Entry", { payment_type: "Pay", company: S.company }, null, [["Purchase", () => go("purchase", "purchase")]]),
		"cash-give": () => pickProject("Give cash to site", "Pick the site.", [["Cash Flow", () => go("cash-give", "cash")]], (p) => viewCash(p, "give")),
		"cash-expense": () => pickProject("Site expense", "Pick the site.", [["Cash Flow", () => go("cash-give", "cash")]], (p) => viewCash(p, "expense")),
	};
	S.current = () => go(key, menuId);
	return (V[kind] || viewHome)();
}

// ------------------------------------------------------------------ SALES + PURCHASE: orders with MS lines, milestone bills, non-MS bills
const KD = {
	sales: { title: "Sales", menu: "sales", order: "Sales Order", inv: "Sales Invoice", party: "Customer", who: "customer",
		msKey: "sales", nonKey: "sales-nonms", newKey: "so-new", word: "sales order", bill: "invoice" },
	purchase: { title: "Purchase", menu: "purchase", order: "Purchase Order", inv: "Purchase Invoice", party: "Supplier", who: "supplier",
		msKey: "po-bill", nonKey: "po-nonms", newKey: "po-new", word: "purchase order", bill: "purchase bill" },
};
const UOM_LABEL = { "Square Foot": "sq.ft", "Square Meter": "sq.m", "Running Meter": "rmt", "Cubic Meter": "cu.m", "Lump Sum": "LS", "Sq Feet": "sq.ft (Sq Feet)", "Sqm": "sq.m (Sqm)" };
function ordersBack(p, kind, mode) {
	const k = KD[kind];
	return [[k.title, () => go(mode === "nonms" ? k.nonKey : k.msKey, k.menu)], [pLabel(p), () => viewOrders(p, kind, mode || "ms")]];
}
// old name kept for the other screens that link back to billing
function salesBack(p) { return ordersBack(p, "sales", "ms"); }
function viewMilestones(p) { return viewOrders(p, "sales", "ms"); }

function directSales(p) {
	setMenu("sales");
	return frameNew("Sales Invoice", { company: p.company || S.company, project: p.name, sbi_direct_invoice: 1 }, null, ordersBack(p, "sales", "ms"));
}

async function viewOrders(p, kind, mode) {
	const k = KD[kind];
	S.here = () => viewOrders(p, kind, mode);
	setMenu(k.menu);
	crumbs([[k.title, () => go(mode === "nonms" ? k.nonKey : k.msKey, k.menu)], [pLabel(p), null]]);
	loading();
	const d = await call("orders", { kind: kind, project: p.name });
	const orders = d.orders || [];
	let h = `<h2 class="t">${esc(pLabel(p))}</h2>
		<div class="sub">${mode === "nonms" ? `Lines with <b>MS = No</b> are not part of any milestone. Bill them here whenever the work is done.`
			: `Lines with <b>MS = Yes</b> are billed by milestone. Click a milestone card to make its ${k.bill}.`}</div>
		<div class="bar"><div class="seg">
			<a class="${mode !== "nonms" ? "on" : ""}" data-act="o-mode" data-kind="${kind}" data-mode="ms" data-p="${esc(p.name)}">Milestone (MS) bills</a>
			<a class="${mode === "nonms" ? "on" : ""}" data-act="o-mode" data-kind="${kind}" data-mode="nonms" data-p="${esc(p.name)}">Non-MS bills</a></div>
			<button class="btn" data-act="o-new" data-kind="${kind}" data-p="${esc(p.name)}">＋ New ${k.word}</button></div>`;
	if (!orders.length) {
		h += `<div class="box msempty"><div class="ico">🧾</div><h3>This project has no ${k.word} yet</h3>
			<div class="muted">Make the ${k.word} once: one line per item with area, unit, cost per unit, and <b>MS</b> Yes / No.<br>
			MS = Yes lines are billed by milestones. MS = No lines are billed separately as non-MS bills.</div>
			<div class="bar c"><button class="btn pri big" data-act="o-new" data-kind="${kind}" data-p="${esc(p.name)}">＋ Create ${k.word}</button>
			${kind === "sales" ? `<button class="btn" data-act="direct-si" data-p="${esc(p.name)}">Make a direct invoice instead</button>`
				: `<button class="btn" data-act="p-buy" data-p="${esc(p.name)}">Purchase from BOQ instead</button>`}</div></div>`;
	}
	orders.forEach((o) => {
		const head = `<h3>${esc(o.name)} <span class="muted">${esc(o.party)} · ${money(o.grand_total)} with GST · billed ${Math.round(o.per_billed || 0)}%</span>
			<a class="muted" data-act="open" data-dt="${k.order}" data-name="${esc(o.name)}">open order</a></h3>
			<div class="chips"><span class="chip ms">MS work ${money(o.ms_net)}</span><span class="chip non">Non-MS ${money(o.non_net)}</span></div>`;
		if (o.docstatus === 0) {
			h += `<div class="box mswait"><div class="ico">⏳</div><div><b>${esc(o.name)} is waiting for your “Submit”.</b>
				<div class="muted">${esc(o.party)} · ${money(o.grand_total)} · ${o.lines.length} line(s). Open it, check it, then click <b>Submit</b>. Billing starts after that.</div></div>
				<button class="btn pri" data-act="open" data-dt="${k.order}" data-name="${esc(o.name)}">Open and submit</button></div>`;
			return;
		}
		h += `<div class="box">${head}`;
		if (mode === "nonms") {
			const non = o.lines.filter((l) => Number(l.ms) === 0);
			if (!non.length) { h += `<div class="hint">No MS = No lines in this order. Everything is billed by milestone.</div></div>`; return; }
			let pend = 0;
			h += `<table><thead><tr><th>Sl</th><th>Description</th><th class="r">Area / Qty</th><th>Unit</th><th class="r">Cost / unit</th><th class="r">Total</th><th class="r">Billed</th><th class="r">To bill</th></tr></thead><tbody>`;
			non.forEach((l) => {
				const left = Math.max(0, (l.amount || 0) - (l.billed || 0));
				pend += left;
				h += `<tr><td>${esc(l.sl || l.idx)}</td><td>${esc(l.description)}</td><td class="r">${Number(l.qty)}</td><td>${esc(UOM_LABEL[l.uom] || l.uom)}</td>
					<td class="r">${money(l.rate)}</td><td class="r">${money(l.amount)}</td><td class="r">${money(l.billed)}</td><td class="r"><b>${money(left)}</b></td></tr>`;
			});
			h += `</tbody></table><div class="bar">`;
			const dr = (o.nonms_invoices || []).filter((x) => x.docstatus === 0);
			if (dr.length) h += `<button class="btn pri" data-act="open" data-dt="${k.inv}" data-name="${esc(dr[0].name)}">Open draft non-MS bill ${esc(dr[0].name)}</button>`;
			else if (pend > 0.5) h += `<button class="btn pri" data-act="o-nonms" data-kind="${kind}" data-o="${esc(o.name)}" data-p="${esc(p.name)}">Make non-MS ${k.bill} (${money(pend)} before GST)</button>`;
			else h += `<span class="pill green">All non-MS lines billed</span>`;
			(o.nonms_invoices || []).filter((x) => x.docstatus === 1).forEach((x) => { h += ` <a class="pill" data-act="open" data-dt="${k.inv}" data-name="${esc(x.name)}">${esc(x.name)}</a>`; });
			h += `</div><div class="muted small">The bill opens with what is left. You can lower the quantity if only part of the work is done.</div></div>`;
			return;
		}
		const terms = (o.terms || []).filter((t) => !t.non_ms);
		if (!o.ms_net) { h += `<div class="hint">No MS = Yes lines in this order. Use “Non-MS bills”.</div></div>`; return; }
		if (!terms.length) { h += `<div class="warn">This order has no milestones (payment terms). Make a new ${k.word} from Lite ERP, or add a Payment Terms Template to it.</div></div>`; return; }
		h += `<div class="cards">`;
		terms.forEach((t) => {
			const inv = t.invoice || t.draft_invoice;
			const state = t.invoice ? `<span class="pill green">Billed</span>` : t.draft_invoice ? `<span class="pill orange">Draft bill</span>` : `<span class="pill blue">Ready to bill</span>`;
			h += `<div class="card ms ${t.invoice ? "done ms-done" : t.draft_invoice ? "ms-draft" : "ms-ready"}" data-act="${inv ? "open" : "o-bill"}" data-dt="${k.inv}" data-name="${esc(inv || "")}"
					data-kind="${kind}" data-o="${esc(o.name)}" data-row="${esc(t.row_name)}" data-p="${esc(p.name)}">
				<div class="n">${t.idx}. ${esc(t.stage || t.payment_term || t.description)}</div>
				<div class="c">${t.pct}% of MS work${t.due_date ? " · bill on " + dt(t.due_date) : ""}</div>
				<div class="f"><b>${money(t.amount)}</b><span>before GST</span></div>
				<div class="f">${state}<span>${inv ? esc(inv) : "click to create"}</span></div>
				${t.received ? `<div class="c">received ${money(t.received)}</div>` : ""}
			</div>`;
		});
		h += `</div></div>`;
	});
	if (kind === "sales" && orders.length) h += `<div class="bar"><button class="btn" data-act="direct-si" data-p="${esc(p.name)}">+ Direct invoice for this project</button></div>`;
	if ((d.invoices || []).length) {
		h += `<div class="box"><h3>${k.inv}s of this project</h3><table><thead><tr><th>Bill</th><th>Date</th><th>${k.party}</th><th>Milestone</th>
			<th class="r">Amount</th><th class="r">Outstanding</th><th>Status</th></tr></thead><tbody>`;
		d.invoices.forEach((i) => {
			h += `<tr class="click" data-act="open" data-dt="${k.inv}" data-name="${esc(i.name)}"><td>${esc(i.name)}</td><td>${dt(i.posting_date)}</td><td>${esc(i.party)}</td>
				<td>${esc(i.stage)}</td><td class="r">${money(i.grand_total)}</td><td class="r">${money(i.outstanding_amount)}</td><td>${statusPill(i.status, i.docstatus)}</td></tr>`;
		});
		h += `</tbody></table></div>`;
	}
	showView(h);
}

async function orderBill(el, act) {
	const p = findProject(el.dataset.p);
	const kind = el.dataset.kind;
	frappe.dom.freeze(__("Making the bill…"));
	try {
		const r = await call(act, { kind: kind, order: el.dataset.o, row: el.dataset.row || "" });
		frappe.dom.unfreeze();
		if (r.existing) frappe.show_alert({ message: __("A bill was already started: {0}", [r.name]), indicator: "orange" }, 5);
		frameForm(r.doctype, r.name, ordersBack(p, kind, act === "nonms_bill" ? "nonms" : "ms"));
	} catch (e) { frappe.dom.unfreeze(); }
}

// ---- new order form: lines (Sl, description, area, unit, cost/unit, total, MS) + milestones of the MS work
const MS_PRESETS = {
	a: [["Advance", 10], ["Foundation", 30], ["Structure", 40], ["Handover", 20]],
	b: [["Foundation", 30], ["Structure", 40], ["Finishing", 30]],
	c: [["Part 1", 25], ["Part 2", 25], ["Part 3", 25], ["Part 4", 25]],
	d: [["Full work", 100]],
};
function msDates(n) { return Array.from({ length: n }, (_, i) => frappe.datetime.add_days(frappe.datetime.get_today(), 30 * (i + 1))); }
function msPreset(k) {
	const P = MS_PRESETS[k] || MS_PRESETS.b;
	const dd = msDates(P.length);
	S.ms.rows = P.map((x, i) => ({ name: x[0], percent: x[1], due_date: dd[i] }));
	R.querySelectorAll(".imp").forEach((b) => b.classList.remove("on"));
	msRender();
}
function uomOptions(sel) {
	const d = S.ms.d;
	const opt = (u) => `<option value="${esc(u)}" ${u === sel ? "selected" : ""}>${esc(UOM_LABEL[u] || u)}</option>`;
	return (d.uoms || []).map(opt).join("") + ((d.uoms_more || []).length ? `<optgroup label="Other units">${d.uoms_more.map(opt).join("")}</optgroup>` : "");
}
function olBlank() { return { sl: "", description: "", qty: "", uom: (S.ms.d.uoms || [])[0] || "Nos", rate: "", ms: 1 }; }

async function viewOrderForm(p, kind) {
	const k = KD[kind];
	S.here = () => viewOrderForm(p, kind);
	setMenu(k.menu);
	crumbs([[k.title, () => go(k.msKey, k.menu)], [pLabel(p), () => viewOrders(p, kind, "ms")], ["New " + k.word, null]]);
	loading();
	const d = await call("order_setup", { kind: kind, project: p.name });
	S.ms = { p: p, kind: kind, d: d, rows: [], lines: [] };
	for (let i = 0; i < 3; i++) S.ms.lines.push(olBlank());
	S.ms.lines.forEach((l, i) => (l.sl = String(i + 1)));
	const partyOpts = (d.parties || []).map((c) => `<option ${c === d.default_party ? "selected" : ""}>${esc(c)}</option>`).join("");
	const itemOpts = (d.items || []).map((i) => `<option value="${esc(i.name)}" ${i.name === d.default_item ? "selected" : ""}>${esc(i.item_name || i.name)}${i.hsn ? " · HSN " + esc(i.hsn) : ""}</option>`).join("");
	const taxOpts = `<option value="">No GST</option>` + (d.templates || []).map((t) => `<option ${t === d.default_template ? "selected" : ""}>${esc(t)}</option>`).join("");
	const imps = d.imports || [];
	const impBtns = imps.map((m, i) => `<button class="btn sm imp" data-act="ms-import" data-i="${i}">${esc(m.label)} <span class="pill">${m.items.length}</span></button>`).join("");
	showView(`<h2 class="t">New ${k.word} · ${esc(pLabel(p))}</h2>
		<div class="sub">Write one line per item. Mark <b>MS = Yes</b> if the line is billed by milestones, <b>No</b> if it is billed separately.</div>
		<div class="fm"><div class="t"><span class="num">1</span> ${k.party} and GST</div><div class="g g4">
			<label>${k.party}<select id="o-party"><option value="">— choose —</option>${partyOpts}</select></label>
			<label>Item code (HSN for GST)<select id="o-item"><option value="">— choose —</option>${itemOpts}</select></label>
			<label>GST<select id="o-tax">${taxOpts}</select></label>
			<label>Company<input value="${esc(d.company || "")}" disabled></label></div></div>
		<div class="fm"><div class="t"><span class="num">2</span> Lines</div>
			<table class="olt"><thead><tr><th>Sl. No.</th><th>Description</th><th class="r">Area / Qty</th><th>Unit</th><th class="r">Cost per unit (₹)</th><th class="r">Total cost</th><th>MS</th><th></th></tr></thead>
			<tbody id="o-lines"></tbody></table>
			<div class="bar"><button class="btn sm" data-act="ol-add">＋ Add line</button>
				${(d.boq_lines || []).length ? `<button class="btn sm" data-act="ol-boq">Bring ${d.boq_lines.length} line(s) from the project BOQ</button>` : ""}
				<span id="o-tot" class="otot"></span></div></div>
		<div class="fm" id="ms-box"><div class="t"><span class="num">3</span> Milestones of the MS work (saved as payment terms)</div>
			${imps.length ? `<div class="presets imps"><span class="muted">Bring in from:</span>${impBtns}</div>` : ""}
			<div class="presets"><span class="muted">Or quick start:</span>
				<button class="btn sm" data-act="ms-preset" data-k="a">Advance + 3 parts</button>
				<button class="btn sm" data-act="ms-preset" data-k="b">3 parts 30/40/30</button>
				<button class="btn sm" data-act="ms-preset" data-k="c">4 equal parts</button>
				<button class="btn sm" data-act="ms-preset" data-k="d">One bill (100%)</button></div>
			<datalist id="ms-stages">${(d.stages || []).map((s) => `<option value="${esc(s)}">`).join("")}</datalist>
			<table class="mst"><thead><tr><th>#</th><th>Milestone name</th><th class="r">% of MS work</th><th class="r">Amount (before GST)</th><th>Bill on date</th><th></th></tr></thead>
			<tbody id="ms-rows"></tbody></table>
			<div class="bar"><button class="btn sm" data-act="ms-add">＋ Add milestone</button><span id="ms-total" class="mstot"></span></div></div>
		<div class="bar"><button class="btn pri big" data-act="o-save">Create ${k.word}</button>
			<button class="btn" data-act="o-mode" data-kind="${kind}" data-mode="ms" data-p="${esc(p.name)}">Cancel</button></div>
		<div class="hint">After you click <b>Create</b>, the order opens below. Check it and click <b>Submit</b> once. Then MS lines are billed by milestone cards and MS = No lines by “Non-MS bills”.</div>`);
	olRender();
	if (imps.length) msImport(0); else msPreset("b");
}
function olRead() {
	R.querySelectorAll("#o-lines tr").forEach((tr) => {
		const l = S.ms.lines[Number(tr.dataset.i)];
		if (!l) return;
		tr.querySelectorAll("[data-f]").forEach((x) => { l[x.dataset.f] = x.value; });
	});
}
function olRender() {
	const b = q("#o-lines");
	if (!b) return;
	b.innerHTML = S.ms.lines.map((l, i) => `<tr data-i="${i}" class="${String(l.ms) === "0" ? "nonms" : ""}">
		<td><input class="ol-in sl" data-f="sl" value="${esc(l.sl)}"></td>
		<td><input class="ol-in" data-f="description" value="${esc(l.description)}" placeholder="e.g. PEB shed erection"></td>
		<td class="r"><input class="ol-in q" data-f="qty" type="number" min="0" step="any" value="${esc(l.qty)}"></td>
		<td><select class="ol-in" data-f="uom">${uomOptions(l.uom)}</select></td>
		<td class="r"><input class="ol-in q" data-f="rate" type="number" min="0" step="any" value="${esc(l.rate)}"></td>
		<td class="r ol-t">–</td>
		<td><select class="ol-in msel" data-f="ms"><option value="1" ${String(l.ms) !== "0" ? "selected" : ""}>Yes</option><option value="0" ${String(l.ms) === "0" ? "selected" : ""}>No</option></select></td>
		<td><button class="btn sm ghost" data-act="ol-del" data-i="${i}" title="Remove">✕</button></td></tr>`).join("");
	olTotals();
}
function olTotals() {
	let msn = 0, non = 0;
	R.querySelectorAll("#o-lines tr").forEach((tr) => {
		const v = (f) => (tr.querySelector(`[data-f="${f}"]`) || {}).value;
		const t = Number(v("qty") || 0) * Number(v("rate") || 0);
		const isMs = v("ms") !== "0";
		tr.classList.toggle("nonms", !isMs);
		tr.querySelector(".ol-t").textContent = t ? money(t) : "–";
		if (isMs) msn += t; else non += t;
	});
	S.ms.msNet = msn;
	const el = q("#o-tot");
	if (el) el.innerHTML = `<span class="chip ms">MS work ${money(msn)}</span><span class="chip non">Non-MS ${money(non)}</span><b>Order ${money(msn + non)}</b> <span class="muted">before GST</span>`;
	const box = q("#ms-box");
	if (box) box.classList.toggle("dim", !msn);
	msTotals();
}
function olFromBoq() {
	olRead();
	const keep = S.ms.lines.filter((l) => (l.description || "").trim() || Number(l.qty) || Number(l.rate));
	const add = (S.ms.d.boq_lines || []).map((b, i) => ({ sl: b.sl || String(keep.length + i + 1), description: b.description, qty: b.qty, uom: b.uom, rate: b.rate, ms: 1 }));
	S.ms.lines = keep.concat(add);
	olRender();
	frappe.show_alert({ message: __("{0} line(s) added from the BOQ. Set MS = No for lines billed separately.", [add.length]), indicator: "blue" }, 6);
}
function msImport(i) {
	const m = (S.ms.d.imports || [])[i];
	if (!m || !m.items.length) return;
	const today = frappe.datetime.get_today();
	const tot = m.items.reduce((a, x) => a + (Number(x.weight) || 0), 0);
	let used = 0;
	S.ms.rows = m.items.map((x, k) => {
		let pc = tot > 0 ? Math.round((Number(x.weight) || 0) / tot * 10000) / 100 : Math.round(10000 / m.items.length) / 100;
		if (k === m.items.length - 1) pc = Math.round((100 - used) * 100) / 100;
		used += pc;
		const due = x.due_date && x.due_date >= today ? x.due_date : frappe.datetime.add_days(today, 30 * (k + 1));
		return { name: x.name, percent: pc, due_date: due };
	});
	R.querySelectorAll(".imp").forEach((b) => b.classList.toggle("on", b.dataset.i === String(i)));
	msRender();
}
function msRead() {
	R.querySelectorAll("#ms-rows tr").forEach((tr) => {
		const r = S.ms.rows[Number(tr.dataset.i)];
		if (!r) return;
		r.name = tr.querySelector(".ms-n").value;
		r.percent = Number(tr.querySelector(".ms-p").value || 0);
		r.due_date = tr.querySelector(".ms-d").value;
	});
}
function msTotals() {
	const v = Number(S.ms.msNet || 0);
	let tot = 0;
	R.querySelectorAll("#ms-rows tr").forEach((tr) => {
		const pc = Number(tr.querySelector(".ms-p").value || 0);
		tot += pc;
		tr.querySelector(".ms-a").textContent = v ? money(v * pc / 100) : "–";
	});
	tot = Math.round(tot * 100) / 100;
	const el = q("#ms-total");
	if (!el) return tot;
	const ok = Math.abs(tot - 100) < 0.01;
	el.className = "mstot " + (ok ? "ok" : "bad");
	el.innerHTML = ok ? `✔ Total 100% · ${money(v)}` : `Total ${tot}% – must be 100% (${tot < 100 ? "add " + Math.round((100 - tot) * 100) / 100 + "% more" : "remove " + Math.round((tot - 100) * 100) / 100 + "%"})`;
	return tot;
}
function msRender() {
	const b = q("#ms-rows");
	if (!b) return;
	b.innerHTML = S.ms.rows.map((r, i) => `<tr data-i="${i}"><td>${i + 1}</td>
		<td><input class="ms-in ms-n" list="ms-stages" value="${esc(r.name)}" placeholder="e.g. Foundation"></td>
		<td class="r"><input class="ms-in ms-p q" type="number" min="0" max="100" step="0.01" value="${r.percent || ""}"></td>
		<td class="r ms-a">–</td>
		<td><input class="ms-in ms-d" type="date" min="${frappe.datetime.get_today()}" value="${esc(r.due_date || "")}"></td>
		<td><button class="btn sm ghost" data-act="ms-del" data-i="${i}" title="Remove">✕</button></td></tr>`).join("");
	msTotals();
}
async function orderSave(btn) {
	olRead(); msRead(); olTotals();
	const { p, kind } = S.ms;
	const k = KD[kind];
	const lines = S.ms.lines.filter((l) => (l.description || "").trim() || Number(l.qty) || Number(l.rate));
	const args = { kind: kind, project: p.name, party: q("#o-party").value, item: q("#o-item").value, template: q("#o-tax").value,
		lines: JSON.stringify(lines), rows: JSON.stringify(S.ms.msNet ? S.ms.rows : []) };
	if (!args.party) return frappe.msgprint(__("Step 1: choose the {0}.", [k.who]));
	if (!args.item) return frappe.msgprint(__("Step 1: choose the item code (it carries the HSN for GST)."));
	if (!lines.length) return frappe.msgprint(__("Step 2: add at least one line."));
	const bad = lines.find((l) => !(l.description || "").trim() || !(Number(l.qty) > 0));
	if (bad) return frappe.msgprint(__("Step 2: every line needs a description and an area / quantity."));
	if (S.ms.msNet && Math.abs(msTotals() - 100) > 0.01) return frappe.msgprint(__("Step 3: the milestones must add up to 100% of the MS work."));
	btn.disabled = true;
	try {
		const r = await call("order_create", args);
		frappe.show_alert({ message: __("{0} made with {1} line(s) and {2} milestone(s). Check it and click Submit.", [r.name, r.lines, r.milestones]), indicator: "green" }, 8);
		frameForm(r.doctype, r.name, ordersBack(p, kind, "ms"));
	} catch (x) { btn.disabled = false; }
}

// ------------------------------------------------------------------ PURCHASE: project -> stage -> BOQ items -> bill
function purchaseBack(p, direct) {
	return [["Purchase", () => go(direct ? "purchase-direct" : "purchase", "purchase")], [pLabel(p), () => viewStages(p, direct)]];
}

async function viewStages(p, direct) {
	S.here = () => viewStages(p, direct);
	setMenu("purchase");
	crumbs([["Purchase", () => go(direct ? "purchase-direct" : "purchase", "purchase")], [pLabel(p), null]]);
	loading();
	const d = await call("purchase_stages", { project: p.name });
	const stages = d.stages || [];
	let h = `<h2 class="t">${esc(pLabel(p))} — pick the stage</h2>
		<div class="sub">${direct ? "A blank purchase bill opens with project and stage filled in." :
			d.boq ? "Click a stage to see its BOQ items not yet bought. Use “Direct bill” for anything outside the BOQ." :
			"This project has no Project BOQ yet, so bills open blank with project and stage filled in."}</div>`;
	h += `<div class="cards">`;
	if (!direct && d.boq) {
		h += `<div class="card" data-act="boq" data-p="${esc(p.name)}" data-stage=""><div class="n">All stages</div><div class="c">Whole BOQ ${esc(d.boq)}</div></div>`;
	}
	stages.forEach((s) => {
		const useBoq = !direct && s.from_boq;
		h += `<div class="card" data-act="${useBoq ? "boq" : "direct-pi"}" data-p="${esc(p.name)}" data-stage="${esc(s.stage)}">
			<div class="n">${esc(s.stage)}</div>
			<div class="c">${s.from_boq ? s.lines + " BOQ line(s) · material " + money(s.material) : "not in BOQ"}</div>
			<div class="f"><span>bought</span><b>${money(s.purchased)}</b></div>
			${s.material ? progress(s.purchased, s.material, s.purchased > s.material ? "over" : "") : ""}
			<div class="f"><span>${s.bills} bill(s)</span>${useBoq ? `<a data-act="direct-pi" data-p="${esc(p.name)}" data-stage="${esc(s.stage)}">Direct bill</a>` : `<span class="pill blue">blank bill</span>`}</div>
		</div>`;
	});
	h += `<div class="card" data-act="direct-pi" data-p="${esc(p.name)}" data-stage=""><div class="n">No stage</div>
		<div class="c">General purchase for this project</div>
		<div class="f"><span>${(d.no_stage || {}).bills || 0} bill(s)</span><b>${money((d.no_stage || {}).purchased)}</b></div></div>`;
	h += `</div>`;
	if (!stages.length) h += `<div class="hint">No stages found for this project (from its BOQ or tasks).</div>`;
	showView(h);
}

async function viewBoq(p, stage) {
	S.here = () => viewBoq(p, stage);
	setMenu("purchase");
	const back = purchaseBack(p, false);
	crumbs(back.concat([[stage || "All stages", null]]));
	loading();
	const d = await call("boq_pending", { project: p.name, stage: stage });
	S.boq = { p: p, stage: stage, cc: d.cost_center, company: d.company || p.company || S.company, rows: d.rows || [] };
	const open = S.boq.rows.filter((r) => r.pending > 0.0005);
	const closed = S.boq.rows.filter((r) => r.pending <= 0.0005);
	const row = (r, i, on) => `<tr class="${on ? "" : "off"}">
		<td><input type="checkbox" class="b-pick" data-i="${i}" ${on ? "checked" : ""}></td>
		<td><b>${esc(r.item_name)}</b><div class="muted">${esc(r.item_code)}${r.activities ? " · " + esc(r.activities).slice(0, 80) : ""}</div></td>
		<td>${esc(r.uom)}</td><td class="r">${num(r.required)}</td><td class="r">${num(r.purchased)}</td>
		<td class="r">${r.in_draft ? `<span class="pill orange">${num(r.in_draft)}</span>` : "0"}</td><td class="r"><b>${num(r.pending)}</b></td>
		<td class="r"><input class="q b-qty" data-i="${i}" type="number" step="any" min="0" value="${on ? Math.round(r.pending * 1000) / 1000 : ""}"></td>
		<td class="r"><input class="q b-rate" data-i="${i}" type="number" step="any" min="0" value="${r.rate || ""}"></td></tr>`;
	let h = `<h2 class="t">${esc(pLabel(p))} · ${esc(stage || "All stages")}</h2>
		<div class="sub">BOQ materials still to buy (needed − already on purchase bills). Tick, adjust quantity or rate, then create the bill.
		The supplier and bill number are filled in on the bill.</div>
		<div class="bar"><button class="btn pri" data-act="make-pi">Create purchase bill with ticked items</button>
		<button class="btn" data-act="direct-pi" data-p="${esc(p.name)}" data-stage="${esc(stage)}">Direct bill (not from BOQ)</button>
		<span class="muted" id="b-total"></span></div>`;
	if (!d.boq) h += `<div class="warn">No Project BOQ for this project. Import the BOQ, or use Direct bill.</div>`;
	if (S.boq.rows.length) {
		h += `<div class="box"><table><thead><tr><th><input type="checkbox" id="b-all" checked></th><th>Item</th><th>Unit</th><th class="r">Needed</th><th class="r">Bought</th>
			<th class="r">In draft bills</th><th class="r">To buy</th><th class="r">Qty on this bill</th><th class="r">Rate</th></tr></thead><tbody>`;
		S.boq.rows.forEach((r, i) => { if (r.pending > 0.0005) h += row(r, i, true); });
		h += `</tbody></table>${!open.length ? `<div class="hint">Everything in the BOQ for this stage is already on purchase bills.</div>` : ""}</div>`;
		if (closed.length) {
			h += `<details><summary>${closed.length} item(s) already fully bought</summary><div class="box"><table><tbody>`;
			S.boq.rows.forEach((r, i) => { if (r.pending <= 0.0005) h += row(r, i, false); });
			h += `</tbody></table></div></details>`;
		}
	} else if (d.boq) {
		h += `<div class="hint">No material items are linked to the BOQ activities for this stage (Site Activity → resources → item).</div>`;
	}
	if ((d.other || []).length) {
		h += `<details><summary>${d.other.length} other BOQ line(s) (typed lines, subcontract, labour, equipment) \u2014 buy these with a direct bill</summary><div class="box"><table>
			<thead><tr><th>Activity</th><th>Unit</th><th class="r">Qty</th><th class="r">Subcontract</th><th class="r">Labour</th><th class="r">Equipment</th><th class="r">Amount</th></tr></thead><tbody>`;
		d.other.forEach((o) => {
			h += `<tr><td>${esc(o.description || o.activity)}${o.type ? ` <span class="pill">${esc(o.type)}</span>` : ""}</td><td>${esc(o.unit)}</td><td class="r">${num(o.qty)}</td><td class="r">${money(o.subcontract_amount)}</td>
				<td class="r">${money(o.labour_amount)}</td><td class="r">${money(o.equipment_amount)}</td><td class="r">${money(o.amount)}</td></tr>`;
		});
		h += `</tbody></table></div></details>`;
	}
	showView(h);
	boqTotal();
}

function boqTotal() {
	let t = 0, n = 0;
	R.querySelectorAll(".b-pick:checked").forEach((c) => {
		const i = c.dataset.i;
		const qv = Number((R.querySelector(`.b-qty[data-i="${i}"]`) || {}).value || 0);
		const rv = Number((R.querySelector(`.b-rate[data-i="${i}"]`) || {}).value || 0);
		if (qv > 0) { t += qv * rv; n++; }
	});
	const el = q("#b-total");
	if (el) el.textContent = n ? n + " item(s), about " + money(t) + " before tax" : "";
}

function purchaseValues(p, stage, company) {
	const v = { company: company || p.company || S.company, project: p.name, sbi_stage: stage };
	return v;
}

async function makePurchaseFromBoq() {
	const b = S.boq;
	const items = [];
	R.querySelectorAll(".b-pick:checked").forEach((c) => {
		const i = Number(c.dataset.i);
		const qv = Number((R.querySelector(`.b-qty[data-i="${i}"]`) || {}).value || 0);
		const rv = Number((R.querySelector(`.b-rate[data-i="${i}"]`) || {}).value || 0);
		if (qv > 0) items.push({ item_code: b.rows[i].item_code, qty: qv, rate: rv });
	});
	if (!items.length) { frappe.msgprint(__("Tick at least one item with a quantity.")); return; }
	await frameNew("Purchase Invoice", purchaseValues(b.p, b.stage, b.company), async (frm, w) => {
		if (b.stage && frm.fields_dict.sbi_project_stage) {
			const ok = await w.frappe.db.exists("Project Stage", b.stage);
			if (ok) await frm.set_value("sbi_project_stage", b.stage);
		}
		frm.clear_table("items");
		frm.refresh_field("items");
		for (const it of items) {
			const row = frm.add_child("items");
			await w.frappe.model.set_value(row.doctype, row.name, "item_code", it.item_code);
			try { await waitFor(() => row.item_name && row.uom, 6000); } catch (e) { /* carry on */ }
			const vals = { qty: it.qty, project: b.p.name };
			if (it.rate) vals.rate = it.rate;
			if (b.cc) vals.cost_center = b.cc;
			await w.frappe.model.set_value(row.doctype, row.name, vals);
		}
		frm.refresh_field("items");
		frm.scroll_to_field && frm.scroll_to_field("supplier");
		w.frappe.show_alert({ message: __("Fill in the supplier and bill number, then Save."), indicator: "blue" }, 6);
	}, purchaseBack(b.p, false).concat([[b.stage || "All stages", () => viewBoq(b.p, b.stage)]]));
}

async function directPurchase(p, stage, direct) {
	setMenu("purchase");
	await frameNew("Purchase Invoice", purchaseValues(p, stage), async (frm, w) => {
		if (stage && frm.fields_dict.sbi_project_stage) {
			const ok = await w.frappe.db.exists("Project Stage", stage);
			if (ok) await frm.set_value("sbi_project_stage", stage);
		}
		(frm.doc.items || []).forEach((r) => { if (!r.project) r.project = p.name; });
		frm.refresh_field("items");
	}, purchaseBack(p, direct));
}

// ------------------------------------------------------------------ CASH FLOW
async function viewCash(p, mode) {
	S.here = () => viewCash(p, mode);
	setMenu("cash");
	crumbs([["Cash Flow", () => go("cash-give", "cash")], [pLabel(p), null]]);
	loading();
	const s = await call("project_cash", { project: p.name });
	const today = frappe.datetime.get_today();
	let h = `<h2 class="t">${esc(pLabel(p))} — site cash</h2><div class="sub">&nbsp;</div>
		<div class="tiles">
			<div class="tile"><div class="l">Cash given to site</div><div class="v">${money(s.given)}</div></div>
			<div class="tile"><div class="l">Spent from site cash</div><div class="v">${money(s.spent)}</div></div>
			<div class="tile"><div class="l">Cash with site</div><div class="v ${s.balance < 0 ? "neg" : ""}">${money(s.balance)}</div></div>
			<div class="tile"><div class="l">Expenses paid by office</div><div class="v">${money(s.office)}</div></div>
			<div class="tile"><div class="l">Petty cash vouchers</div><div class="v">${money(s.petty)}</div></div></div>
		<div class="forms">
			<div class="fm ${mode === "give" ? "hl" : ""}"><div class="t">Give cash to site</div><div class="g">
				<input type="date" id="c-date" value="${today}"><input type="number" id="c-amount" placeholder="Amount" min="0" step="0.01">
				<input type="text" id="c-who" placeholder="Received by" class="full"><input type="text" id="c-remarks" placeholder="Remarks" class="full"></div>
				<button class="btn pri" data-act="add-cash" data-p="${esc(p.name)}">Save</button></div>
			<div class="fm ${mode === "expense" ? "hl" : ""}"><div class="t">Site expense</div><div class="g">
				<input type="date" id="e-date" value="${today}"><input type="number" id="e-amount" placeholder="Amount" min="0" step="0.01">
				<select id="e-cat"><option>Transport</option><option>Equipment</option><option>Subcontract</option><option>Other</option></select>
				<select id="e-src"><option value="Site Cash">Paid from site cash</option><option value="Office">Paid by office</option></select>
				<input type="text" id="e-party" placeholder="Paid to" class="full"><input type="text" id="e-desc" placeholder="What for" class="full"></div>
				<button class="btn pri" data-act="add-expense" data-p="${esc(p.name)}">Save</button></div></div>`;
	if ((s.recent || []).length) {
		h += `<div class="box"><h3>Latest entries</h3><table><thead><tr><th>Date</th><th>Entry</th><th>Type</th><th>Person / party</th><th>Note</th><th class="r">Amount</th></tr></thead><tbody>`;
		s.recent.forEach((r) => {
			h += `<tr class="click" data-act="open" data-dt="${esc(r.dt)}" data-name="${esc(r.name)}"><td>${dt(r.d)}</td><td>${esc(r.name)}${r.je ? ` <span class="pill">Tally</span>` : ""}</td>
				<td>${esc(r.kind)}</td><td>${esc(r.who)}</td><td>${esc((r.note || "").split("\n")[0].slice(0, 80))}</td><td class="r">${money(r.amount)}</td></tr>`;
		});
		h += `</tbody></table></div>`;
	}
	showView(h);
	const f = q(mode === "expense" ? "#e-amount" : "#c-amount");
	if (f) f.focus();
}

function periodRange(p) {
	const t = new Date();
	const y = t.getFullYear(), m = t.getMonth();
	const d = (Y, M, D) => frappe.datetime.obj_to_str(new Date(Y, M, D));
	const fy = m >= 3 ? y : y - 1;
	const qs = Math.floor(m / 3) * 3;
	if (p === "month") return [d(y, m, 1), d(y, m + 1, 0)];
	if (p === "last_month") return [d(y, m - 1, 1), d(y, m, 0)];
	if (p === "quarter") return [d(y, qs, 1), d(y, qs + 3, 0)];
	if (p === "last_quarter") return [d(y, qs - 3, 1), d(y, qs, 0)];
	if (p === "last_fy") return [d(fy - 1, 3, 1), d(fy, 3, 0)];
	if (p === "custom") return [S.from || d(fy, 3, 1), S.to || d(fy + 1, 3, 0)];
	return [d(fy, 3, 1), d(fy + 1, 3, 0)];
}

function periodBar(extra) {
	const opts = [["month", "This month"], ["last_month", "Last month"], ["quarter", "This quarter"], ["last_quarter", "Last quarter"],
		["fy", "This financial year"], ["last_fy", "Last financial year"], ["custom", "Custom dates"]];
	const r = periodRange(S.period);
	return `<div class="bar"><select id="period">${opts.map((o) => `<option value="${o[0]}" ${S.period === o[0] ? "selected" : ""}>${o[1]}</option>`).join("")}</select>
		<span class="${S.period === "custom" ? "" : "hide"}" id="pcustom"><input type="date" id="pfrom" value="${r[0]}"> to <input type="date" id="pto" value="${r[1]}"></span>
		${extra || ""}</div>`;
}

async function viewTally() {
	S.here = viewTally;
	setMenu("cash");
	crumbs([["Cash Flow", () => go("cash-give", "cash")], ["Import from Tally", null]]);
	S.current = viewTally;
	loading();
	const r = periodRange(S.period);
	const d = await call("tally_cash", { from_date: r[0], to_date: r[1], include_bank: S.includeBank ? 1 : 0 });
	const rows = d.rows || [];
	const plist = projectsForCompany();
	let h = `<h2 class="t">Import from Tally</h2><div class="sub">Tally cash payments that are not yet on a site. Tick them, pick the site, and add.</div>
		${periodBar(`<label class="muted"><input type="checkbox" id="t-bank" ${S.includeBank ? "checked" : ""}> include bank payments</label>`)}
		<div class="bar"><select id="t-project"><option value="">— site / project —</option>${plist.map((p) => `<option value="${esc(p.name)}">${esc(pLabel(p))} (${esc(p.name)})</option>`).join("")}</select>
		<button class="btn pri" data-act="import-tally">Add ticked to this site</button><span class="muted">${rows.length} payment(s)</span></div>`;
	if (rows.length) {
		h += `<div class="box"><table><thead><tr><th><input type="checkbox" id="t-all"></th><th>Date</th><th>Tally voucher</th><th>Paid to</th><th>Narration</th><th class="r">Amount</th><th>Add as</th></tr></thead><tbody>`;
		rows.forEach((x) => {
			h += `<tr><td><input type="checkbox" class="t-pick" data-je="${esc(x.name)}"></td><td>${dt(x.posting_date)}</td>
				<td><a data-act="open" data-dt="Journal Entry" data-name="${esc(x.name)}">${esc(x.tally_voucher || x.name)}</a></td><td>${esc(x.paid_to)}</td>
				<td>${esc((x.remark || "").slice(0, 90))}</td><td class="r">${money(x.amount)}</td>
				<td><select class="t-kind" data-je="${esc(x.name)}"><option value="Cash">Cash given to site</option><option value="Transport">Expense: Transport</option>
				<option value="Equipment">Expense: Equipment</option><option value="Subcontract">Expense: Subcontract</option><option value="Other">Expense: Other</option></select></td></tr>`;
		});
		h += `</tbody></table></div>`;
	} else {
		h += `<div class="hint">No Tally cash payments waiting in this period.</div>`;
	}
	showView(h);
}

// ------------------------------------------------------------------ PROJECTS / SITE SUMMARY
async function summary() {
	const d = await call("projects_summary", {});
	S.summary = d.projects || [];
	return S.summary;
}

async function viewProjects() {
	S.here = viewProjects;
	setMenu("projects");
	crumbs([["Projects", null]], `<a data-act="go" data-go="new:Project">+ New project</a>`);
	S.current = viewProjects;
	loading();
	const list = await summary();
	let h = `<h2 class="t">Projects</h2><div class="sub">Click a project for its full picture and quick actions.</div>
		<input class="search" id="psearch2" placeholder="Search project or customer…"><div class="cards" id="pcards2">`;
	list.forEach((p) => {
		h += `<div class="card ${p.status !== "Open" ? "done" : ""}" data-act="project" data-p="${esc(p.name)}"
				data-s="${esc((p.name + " " + (p.project_name || "") + " " + (p.customer || "")).toLowerCase())}">
			<div class="n">${esc(pLabel(p))}</div><div class="c">${esc(p.name)}${p.customer ? " · " + esc(p.customer) : ""}${p.current_stage ? " · " + esc(p.current_stage) : ""}</div>
			<div class="f"><span>Value</span><b>${money(p.value)}</b></div>
			${progress(p.billed, p.value)}<div class="f small"><span>billed ${p.value ? Math.round((p.billed || 0) * 100 / p.value) : 0}%</span><span>received ${money(p.received)}</span></div>
			<div class="f"><span>Billed</span><b>${money(p.billed)}</b></div>
			<div class="f"><span>Spent</span><b>${money(p.spent)}</b></div>
			<div class="f"><span>Cash with site</span><b class="${p.cash_balance < 0 ? "neg" : ""}">${money(p.cash_balance)}</b></div>
		</div>`;
	});
	h += `</div>${list.length ? "" : `<div class="hint">No projects.</div>`}`;
	showView(h);
	const s = q("#psearch2");
	s.addEventListener("input", () => {
		const t = s.value.toLowerCase().trim();
		R.querySelectorAll("#pcards2 .card").forEach((c) => c.classList.toggle("hide", !!t && c.dataset.s.indexOf(t) < 0));
	});
}

async function viewProject(name) {
	S.here = () => viewProject(name);
	setMenu("projects");
	const list = S.summary || (await summary());
	const p = list.find((x) => x.name === name) || findProject(name);
	crumbs([["Projects", () => go("projects", "projects")], [pLabel(p), null]]);
	const margin = (p.billed || 0) - (p.spent || 0);
	showView(`<h2 class="t">${esc(pLabel(p))}</h2><div class="sub">${esc(p.name)}${p.customer ? " · " + esc(p.customer) : ""} · ${esc(p.status || "")}</div>
		<div class="tiles">
			<div class="tile"><div class="l">Contract / order value</div><div class="v">${money(p.value)}</div></div>
			<div class="tile"><div class="l">Billed</div><div class="v">${money(p.billed)}</div></div>
			<div class="tile"><div class="l">Received</div><div class="v">${money(p.received)}</div></div>
			<div class="tile"><div class="l">To receive</div><div class="v">${money(p.outstanding)}</div></div>
			<div class="tile"><div class="l">Purchases</div><div class="v">${money(p.purchased)}</div></div>
			<div class="tile"><div class="l">Site + office expenses</div><div class="v">${money((p.site_spent || 0) + (p.office_spent || 0))}</div></div>
			<div class="tile"><div class="l">Cash with site</div><div class="v ${p.cash_balance < 0 ? "neg" : ""}">${money(p.cash_balance)}</div></div>
			<div class="tile"><div class="l">Billed − spent</div><div class="v ${margin < 0 ? "neg" : ""}">${money(margin)}</div></div></div>
		<div class="cards">
			<div class="card" data-act="p-so" data-p="${esc(p.name)}"><div class="n">New sales order</div><div class="c">Lines with area, rate and MS Yes / No</div></div>
			<div class="card" data-act="p-bill" data-p="${esc(p.name)}"><div class="n">Bill a milestone</div><div class="c">Sales invoice from the order’s milestones</div></div>
			<div class="card" data-act="p-po" data-p="${esc(p.name)}"><div class="n">New purchase order</div><div class="c">Supplier / subcontractor order with MS lines</div></div>
			<div class="card" data-act="p-buy" data-p="${esc(p.name)}"><div class="n">Purchase from BOQ</div><div class="c">Stage → items not yet bought</div></div>
			<div class="card" data-act="p-cash" data-p="${esc(p.name)}"><div class="n">Site cash</div><div class="c">Give cash, record expenses</div></div>
			<div class="card" data-act="open" data-dt="Project" data-name="${esc(p.name)}"><div class="n">Open project</div><div class="c">Project form, tasks, stages</div></div>
		</div>`);
}

async function viewSites() {
	S.here = viewSites;
	setMenu("site");
	crumbs([["Site Summary", null]]);
	S.current = viewSites;
	loading();
	const list = await summary();
	const tot = { value: 0, billed: 0, received: 0, outstanding: 0, purchased: 0, other: 0, cash: 0 };
	let h = `<h2 class="t">Site summary</h2><div class="sub">All projects of ${esc(S.company || "all companies")}. Click a row for that site.</div>
		<div class="box"><table><thead><tr><th>Project</th><th>Customer</th><th class="r">Value</th><th class="r">Billed</th><th class="r">Received</th>
		<th class="r">To receive</th><th class="r">Purchases</th><th class="r">Site + office exp.</th><th class="r">Cash with site</th><th class="r">Billed − spent</th></tr></thead><tbody>`;
	list.forEach((p) => {
		const other = (p.site_spent || 0) + (p.office_spent || 0);
		const m = (p.billed || 0) - (p.spent || 0);
		tot.value += p.value || 0; tot.billed += p.billed || 0; tot.received += p.received || 0; tot.outstanding += p.outstanding || 0;
		tot.purchased += p.purchased || 0; tot.other += other; tot.cash += p.cash_balance || 0;
		h += `<tr class="click" data-act="project" data-p="${esc(p.name)}"><td><b>${esc(pLabel(p))}</b><div class="muted">${esc(p.name)}</div></td><td>${esc(p.customer)}</td>
			<td class="r">${money(p.value)}</td><td class="r">${money(p.billed)}${p.value ? progress(p.billed, p.value, "thin") : ""}</td><td class="r">${money(p.received)}</td><td class="r">${money(p.outstanding)}</td>
			<td class="r">${money(p.purchased)}</td><td class="r">${money(other)}</td><td class="r ${p.cash_balance < 0 ? "neg" : ""}">${money(p.cash_balance)}</td>
			<td class="r ${m < 0 ? "neg" : ""}">${money(m)}</td></tr>`;
	});
	const tm = tot.billed - tot.purchased - tot.other;
	h += `<tr class="total"><td>Total</td><td></td><td class="r">${money(tot.value)}</td><td class="r">${money(tot.billed)}</td><td class="r">${money(tot.received)}</td>
		<td class="r">${money(tot.outstanding)}</td><td class="r">${money(tot.purchased)}</td><td class="r">${money(tot.other)}</td><td class="r">${money(tot.cash)}</td>
		<td class="r ${tm < 0 ? "neg" : ""}">${money(tm)}</td></tr></tbody></table></div>`;
	showView(h);
}

async function viewCashPosition() {
	S.here = viewCashPosition;
	setMenu("site");
	crumbs([["Site Summary", () => go("sites", "site")], ["Cash with each site", null]]);
	S.current = viewCashPosition;
	loading();
	const d = await call("cash_position", {});
	let h = `<h2 class="t">Cash with each site</h2><div class="sub">Cash given to the site less expenses paid from site cash.</div>
		<div class="box"><table><thead><tr><th>Project</th><th class="r">Given</th><th class="r">Spent from site cash</th><th class="r">Paid by office</th><th class="r">Cash with site</th></tr></thead><tbody>`;
	let t = 0;
	(d.projects || []).forEach((r) => {
		t += r.balance;
		h += `<tr class="click" data-act="p-cash" data-p="${esc(r.project)}"><td>${esc(pLabel(findProject(r.project)))}</td><td class="r">${money(r.given)}</td>
			<td class="r">${money(r.spent)}</td><td class="r">${money(r.office)}</td><td class="r ${r.balance < 0 ? "neg" : ""}">${money(r.balance)}</td></tr>`;
	});
	h += `<tr class="total"><td>Total</td><td></td><td></td><td></td><td class="r">${money(t)}</td></tr></tbody></table></div>`;
	showView(h);
}

// ------------------------------------------------------------------ GST
async function viewGst() {
	S.here = viewGst;
	setMenu("gst");
	crumbs([["GST", null], ["GST to pay", null]]);
	S.current = viewGst;
	if (!S.company) { showView(`<div class="hint">Pick a company (top right). GST is worked out per GSTIN.</div>`); return; }
	loading();
	const r = periodRange(S.period);
	const g = await call("gst", { from_date: r[0], to_date: r[1] });
	let h = `<h2 class="t">GST — ${esc(S.company)}</h2>${periodBar()}`;
	if (!g.accounts) {
		h += `<div class="warn">No GST accounts found for this company. Add them in GST Settings → GST Accounts.</div>
			<button class="btn" data-act="open" data-dt="GST Settings" data-name="GST Settings">Open GST Settings</button>`;
		showView(h);
		return;
	}
	const t = g.total || {};
	h += `<div class="tiles">
		<div class="tile"><div class="l">Output GST (on sales)</div><div class="v">${money(t.output)}</div></div>
		<div class="tile"><div class="l">Input credit (on purchases)</div><div class="v">${money(t.itc)}</div></div>
		<div class="tile"><div class="l">Net GST for the period</div><div class="v ${t.net < 0 ? "neg" : ""}">${money(t.net)}</div></div>
		<div class="tile"><div class="l">GST paid in cash</div><div class="v">${money(t.cash)}</div></div>
		<div class="tile"><div class="l">${g.to_pay >= 0 ? "Balance GST to pay" : "Input credit carried forward"}</div><div class="v ${g.to_pay > 0 ? "neg" : ""}">${money(Math.abs(g.to_pay || 0))}</div></div></div>
		<div class="muted">Balance as on ${dt(r[1])}: output GST ledgers ${money(g.output_balance)} less input credit ${money(g.itc_balance)}.</div>`;
	if ((g.draft_si || 0) + (g.draft_pi || 0)) {
		h += `<div class="warn">${g.draft_si} sales and ${g.draft_pi} purchase invoice(s) in this period are still draft and not counted until submitted.</div>`;
	}
	if ((g.months || []).length) {
		h += `<div class="box" style="margin-top:12px"><h3>Month by month</h3><table><thead><tr><th>Month</th><th class="r">Output GST</th><th class="r">Input credit</th><th class="r">Net</th>
			<th class="r">Set off from credit</th><th class="r">Paid in cash</th></tr></thead><tbody>`;
		g.months.forEach((m) => {
			h += `<tr><td>${moment(m.month + "-01").format("MMM YYYY")}</td><td class="r">${money(m.output)}</td><td class="r">${money(m.itc)}</td>
				<td class="r ${m.net < 0 ? "neg" : ""}">${money(m.net)}</td><td class="r">${money(m.setoff)}</td><td class="r">${money(m.cash)}</td></tr>`;
		});
		h += `<tr class="total"><td>Total</td><td class="r">${money(t.output)}</td><td class="r">${money(t.itc)}</td><td class="r">${money(t.net)}</td>
			<td class="r">${money(t.setoff)}</td><td class="r">${money(t.cash)}</td></tr></tbody></table></div>`;
	} else {
		h += `<div class="hint">No GST postings in this period.</div>`;
	}
	if ((g.heads || []).length) {
		h += `<div class="box"><h3>By tax head</h3><table><thead><tr><th>Head</th><th class="r">Output</th><th class="r">Input credit</th><th class="r">Net</th></tr></thead><tbody>`;
		g.heads.forEach((x) => {
			h += `<tr><td>${esc(x.head)}</td><td class="r">${money(x.output)}</td><td class="r">${money(x.itc)}</td><td class="r ${x.net < 0 ? "neg" : ""}">${money(x.net)}</td></tr>`;
		});
		h += `</tbody></table></div>`;
	}
	showView(h);
}

// ------------------------------------------------------------------ HOME
function greet() {
	const h = new Date().getHours();
	return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

async function viewHome() {
	S.here = viewHome;
	S.current = viewHome;
	setMenu("home");
	crumbs([["Home", null]], `<span class="muted">${esc(frappe.datetime.str_to_user(frappe.datetime.get_today()))}</span>`);
	if (!S.company) { showView(`<div class="hint">Pick a company (top right).</div>`); return; }
	loading();
	const fy = periodRange("fy");
	const d = await call("home", { fy_from: fy[0] });
	const k = d.kpi || {};
	const name = (frappe.session.user_fullname || "").split(" ")[0];
	const tile = (label, value, sub, go, cls, icon, tone) => `<div class="tile ti-${tone || "blue"} ${go ? "go" : ""}" ${go ? `data-go="${go}"` : ""}>
		<div class="tic">${ICON(icon || "info")}</div><div class="tbody"><div class="l">${label}</div><div class="v ${cls || ""}">${value}</div>${sub ? `<div class="s">${sub}</div>` : ""}</div></div>`;
	const bankStale = !k.bank_last || k.bank_last < frappe.datetime.get_today();
	let h = `<div class="hero"><div><div class="hero-hi">${greet()}${name ? ", " + esc(name) : ""}</div>
			<div class="hero-sub">${esc(S.company)} \u00b7 ${esc(moment().format ? frappe.datetime.str_to_user(frappe.datetime.get_today()) : "")}</div></div>
			<div class="hero-acts"><a class="hero-btn" data-go="sales" data-m="sales">${ICON("receipt")} Bill a milestone</a>
			<a class="hero-btn" data-go="purchase" data-m="purchase">${ICON("cart")} Purchase from BOQ</a>
			<a class="hero-btn ${bankStale ? "warnb" : ""}" data-go="bank-upload" data-m="bank">${ICON("upload")} Upload bank statement</a></div></div>
		<div class="tiles home">
			${tile("Sales billed this month", money(k.billed_month), "this year " + money(k.billed_fy), "list:Sales Invoice", "", "trend", "blue")}
			${tile("Received this month", money(k.received_month), "from customers", "receive", "", "inbox", "green")}
			${tile("To receive from customers", money(k.receivable), k.receivable_overdue ? `<span class="neg">overdue ${money(k.receivable_overdue)}</span>` : "nothing overdue", "report:Accounts Receivable", "", "clock", "amber")}
			${tile("Purchases this month", money(k.purchased_month), "paid " + money(k.paid_month), "list:Purchase Invoice", "", "cart", "violet")}
			${tile("To pay suppliers", money(k.payable), k.payable_overdue ? `<span class="neg">overdue ${money(k.payable_overdue)}</span>` : "nothing overdue", "report:Accounts Payable", "", "outbox", "red")}
			${tile("Bank and cash balance", money(k.bank_cash), "all bank and cash ledgers", "report:General Ledger", "", "bank", "teal")}
			${tile("Cash with sites", money(k.cash_sites), "given less spent", "cash-position", k.cash_sites < 0 ? "neg" : "", "wallet", "amber")}
			<div class="tile ti-red go" data-go="gst" id="home-gst"><div class="tic">${ICON("percent")}</div><div class="tbody"><div class="l">GST to pay</div><div class="v muted">\u2026</div><div class="s">as on today</div></div></div>
			${tile("Site labour today", String(k.labour_today || 0), "punched in", "hr", "", "users", "teal")}
			${tile("Bank statement uploaded", k.bank_last ? dt(k.bank_last) : "never", (k.bank_to_check || 0) + " entries to check", "bank",
				bankStale ? "neg" : "", bankStale ? "alert" : "check", bankStale ? "red" : "green")}
		</div>
		<div class="two"><div class="box"><h3>${ICON("trend")} Sales vs purchases <span class="muted">last 6 months, before tax</span></h3>
			${barChart(d.months || [], ["sales", "purchases"], ["#c8102e", "#64748b"], ["Sales", "Purchases"])}</div>
		<div class="box"><h3>${ICON("clock")} Money owed, by how late</h3>
			${ageBar("To receive from customers", (d.ageing || {}).receive || {}, "report:Accounts Receivable")}
			${ageBar("To pay suppliers", (d.ageing || {}).pay || {}, "report:Accounts Payable")}</div></div>`;
	if ((k.draft_si || 0) + (k.draft_pi || 0)) {
		h += `<div class="warn">${k.draft_si} sales and ${k.draft_pi} purchase invoice(s) are still draft (for example from Tally) and are not in these figures until submitted.</div>`;
	}
	h += `<div class="qa">${[["cash-give", "Give cash to site", "cash"],
		["cash-expense", "Site expense", "cash"], ["receive", "Receive payment", "sales"], ["pay", "Pay supplier", "purchase"],
		["bank", "Daily bank check", "bank"], ["hr", "Today’s attendance", "hr"], ["sites", "Site summary", "site"]]
		.map((x) => `<a class="qa-i" data-go="${x[0]}" data-m="${x[2]}">${esc(x[1])}</a>`).join("")}</div>`;
	h += `<div class="two"><div class="box"><h3>Milestones to bill <span class="muted">due in the next 30 days or overdue</span></h3>`;
	if ((d.milestones || []).length) {
		const today = frappe.datetime.get_today();
		h += `<table><thead><tr><th>Due</th><th>Project</th><th>Milestone</th><th class="r">Amount</th></tr></thead><tbody>`;
		d.milestones.forEach((m) => {
			const late = String(m.due_date) < today;
			h += `<tr class="click" data-act="p-bill" data-p="${esc(m.project || "")}"><td class="${late ? "neg" : ""}">${dt(m.due_date)}</td>
				<td>${esc(pLabel(findProject(m.project || "")))}<div class="muted">${esc(m.customer)}</div></td>
				<td>${esc(m.stage || m.payment_term)}</td><td class="r">${money(m.payment_amount)}</td></tr>`;
		});
		h += `</tbody></table>`;
	} else {
		h += `<div class="hint">No milestones due in the next 30 days.</div>`;
	}
	h += `</div><div class="box"><h3>Latest invoices</h3><table><thead><tr><th>Invoice</th><th>Party</th><th class="r">Amount</th><th>Status</th></tr></thead><tbody>`;
	const rows = (d.sales || []).map((x) => Object.assign({ dt: "Sales Invoice" }, x))
		.concat((d.purchases || []).map((x) => Object.assign({ dt: "Purchase Invoice" }, x)));
	rows.forEach((x) => {
		h += `<tr class="click" data-act="open" data-dt="${x.dt}" data-name="${esc(x.name)}"><td>${esc(x.name)}<div class="muted">${x.dt === "Sales Invoice" ? "Sales" : "Purchase"} · ${dt(x.posting_date)}</div></td>
			<td>${esc(x.party)}${x.project ? `<div class="muted">${esc(pLabel(findProject(x.project)))}</div>` : ""}</td>
			<td class="r">${money(x.grand_total)}</td><td>${statusPill(x.status, x.docstatus)}</td></tr>`;
	});
	if (!rows.length) h += `<tr><td colspan="4" class="hint">No invoices yet.</td></tr>`;
	h += `</tbody></table></div></div>`;
	showView(h);
	// the GST balance is a heavier query - fill it in once the page is showing
	const today = frappe.datetime.get_today();
	call("gst", { from_date: today, to_date: today }).then((g) => {
		const el = q("#home-gst");
		if (!el) return;
		const v = el.querySelector(".v");
		if (!g.accounts) { v.textContent = "not set up"; v.classList.add("muted"); el.querySelector(".s").textContent = "add GST accounts in GST Settings"; return; }
		const tp = g.to_pay || 0;
		el.querySelector(".l").textContent = tp >= 0 ? "GST to pay" : "Input credit carried forward";
		v.className = "v " + (tp > 0 ? "neg" : "");
		v.textContent = money(Math.abs(tp));
	}).catch(() => {});
}

// ------------------------------------------------------------------ HR: attendance for today, a salary month or any dates
const hm = (v) => (v ? String(v).slice(11, 16) : "");
const kmTxt = (m) => (!m ? "" : m >= 1000 ? (Number(m) / 1000).toFixed(2) + " km" : Math.round(m) + " m");
function salaryMonth(startDay, ref, back) {
	// the salary month that contains ref (back = 1 for the month before)
	const sd = Math.min(28, Math.max(1, Number(startDay) || 1));
	const r = frappe.datetime.str_to_obj(ref || frappe.datetime.get_today());
	let y = r.getFullYear(), m = r.getMonth();
	if (sd > 1 && r.getDate() < sd) m -= 1;
	m -= back || 0;
	const s = new Date(y, m, sd);
	const e = new Date(y, m + 1, sd - 1);
	const f = (d) => d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2);
	return [f(s), f(e)];
}
function hrRange() {
	const P = S.hrP || (S.hrP = { mode: "day", day: frappe.datetime.get_today() });
	const sd = (S.hrSet && S.hrSet.start_day) || 1;
	if (P.mode === "month") return salaryMonth(sd, frappe.datetime.get_today(), 0);
	if (P.mode === "prev") return salaryMonth(sd, frappe.datetime.get_today(), 1);
	if (P.mode === "custom" && P.from && P.to) return [P.from, P.to];
	return [P.day || frappe.datetime.get_today(), P.day || frappe.datetime.get_today()];
}
function hrBar() {
	const P = S.hrP;
	const r = hrRange();
	const sd = (S.hrSet && S.hrSet.start_day) || 1;
	const seg = [["day", "Day"], ["month", "This salary month"], ["prev", "Last salary month"], ["custom", "Custom dates"]]
		.map((x) => `<a class="${P.mode === x[0] ? "on" : ""}" data-act="hr-mode" data-mode="${x[0]}">${x[1]}</a>`).join("");
	let extra = "";
	if (P.mode === "day") extra = `<input type="date" id="hr-date" value="${esc(P.day)}"><button class="btn sm" data-act="hr-today">Today</button>`;
	else if (P.mode === "custom") extra = `<input type="date" id="hr-from" value="${esc(P.from || r[0])}"><span class="muted">to</span><input type="date" id="hr-to" value="${esc(P.to || r[1])}">`;
	else extra = `<span class="pill">${dt(r[0])} – ${dt(r[1])}</span>`;
	return `<div class="bar hrbar"><div class="seg">${seg}</div>${extra}
		<a class="muted" data-act="hr-settings" title="Salary month start day, full / half day hours, office location">⚙ Month settings (starts on day ${sd})</a></div>`;
}

async function viewHr(day) {
	if (day) S.hrP = { mode: "day", day: day };
	if (!S.hrP) S.hrP = { mode: "day", day: frappe.datetime.get_today() };
	S.here = () => viewHr();
	S.current = () => viewHr();
	setMenu("hr");
	crumbs([["HR", null], ["Attendance", null]]);
	loading();
	let r = hrRange();
	let d = await call("hr", { from_date: r[0], to_date: r[1] });
	if (!S.hrSet || Number(S.hrSet.start_day) !== Number((d.settings || {}).start_day)) {
		S.hrSet = d.settings || {};
		const r2 = hrRange();
		if (r2[0] !== r[0] || r2[1] !== r[1]) { r = r2; d = await call("hr", { from_date: r[0], to_date: r[1] }); }
	}
	S.hrSet = d.settings || S.hrSet || {};
	const one = r[0] === r[1];
	const e = d.employees || { status: [] };
	const st = {};
	(e.status || []).forEach((s) => (st[s.status] = s.n));
	const sites = d.sites || [];
	const present = sites.reduce((a, s) => a + (s.present || 0), 0);
	const wage = sites.reduce((a, s) => a + Number(s.wage || 0), 0);
	const outside = sites.reduce((a, s) => a + Number(s.outside || 0), 0);
	const office = d.office || [];
	const offDays = office.reduce((a, o) => a + (o.days || 0), 0);
	const offOut = office.reduce((a, o) => a + (o.outside || 0), 0);
	const inNow = office.filter((o) => o.last_type === "IN").length;
	const p = d.pending || {};
	const period = one ? dt(r[0]) : dt(r[0]) + " – " + dt(r[1]);
	let h = `<h2 class="t">Attendance <span class="muted">${period}</span></h2>${hrBar()}
		<div class="tiles">
			<div class="tile"><div class="l">${one ? "Site labour present" : "Site labour-days"}</div><div class="v">${present}</div><div class="s">${one ? "of " + (d.labour_total || 0) + " active labour" : "worker × days, " + (d.labour_total || 0) + " active labour"}</div></div>
			<div class="tile"><div class="l">Labour wages</div><div class="v">${money(wage)}</div><div class="s">daily wage × days present</div></div>
			<div class="tile"><div class="l">Punched outside the site</div><div class="v ${outside ? "neg" : ""}">${outside}</div><div class="s">outside the geofence</div></div>
			<div class="tile go" data-act="hr-office-all"><div class="l">${one ? "Office staff punched" : "Office staff-days"}</div><div class="v">${offDays}</div>
				<div class="s">of ${e.active || 0} staff${one ? " · in office now " + inNow : ""}${offOut ? ` · <b class="neg">${offOut} outside</b>` : ""}</div></div>
			<div class="tile"><div class="l">Staff attendance marked</div><div class="v">${(st["Present"] || 0) + (st["Work From Home"] || 0)}</div>
				<div class="s">half day ${st["Half Day"] || 0} · leave ${st["On Leave"] || 0} · absent ${st["Absent"] || 0}</div></div>
			<div class="tile go" data-go="list:Leave Application" data-m="hr"><div class="l">Leave to approve</div><div class="v">${p.leave || 0}</div></div>
			<div class="tile go" data-go="list:Expense Claim" data-m="hr"><div class="l">Expense claims open</div><div class="v">${p.expense || 0}</div></div>
			<div class="tile go" data-go="list:Employee Advance" data-m="hr"><div class="l">Advances open</div><div class="v">${p.advance || 0}</div></div>
		</div>`;
	// office staff
	h += `<div class="box"><h3>Office staff <span class="muted">punch IN / OUT with GPS and photo · click a name for every punch</span>
		<a class="muted" data-go="ext:/sbi_office" data-m="hr">Open SBI Office app ↗</a></h3>`;
	if (!d.office_ready) h += `<div class="warn">Run the latest Lite ERP installer once to add the office punch fields.</div>`;
	if (!office.length) h += `<div class="hint">No active employees for this company.</div>`;
	else {
		h += `<table><thead><tr><th>Employee</th>${one ? "<th>In</th><th>Out</th><th>Status</th>" : `<th class="r">Days</th><th class="r">Full</th><th class="r">Half</th><th class="r">Late</th><th class="r">No OUT</th>`}
			<th class="r">Hours</th><th>Location</th></tr></thead><tbody>`;
		office.forEach((o) => {
			const status = !o.punches ? (o.no_login ? `<span class="pill orange">no login</span>` : `<span class="pill">not punched</span>`)
				: o.last_type === "IN" ? `<span class="pill green">in office</span>` : `<span class="pill">left</span>`;
			h += `<tr class="click" data-act="hr-emp" data-e="${esc(o.employee)}"><td><b>${esc(o.employee_name || o.employee)}</b><div class="muted">${esc(o.designation || o.employee)}</div></td>
				${one ? `<td>${esc(o.first_in || "–")}${o.late ? ` <span class="pill orange">late</span>` : ""}</td><td>${esc(o.last_out || "–")}</td><td>${status}</td>`
					: `<td class="r"><b>${o.days || 0}</b></td><td class="r">${o.full || 0}</td><td class="r">${o.half || 0}</td><td class="r ${o.late ? "neg" : ""}">${o.late || 0}</td><td class="r ${o.no_out ? "neg" : ""}">${o.no_out || 0}</td>`}
				<td class="r">${o.hours ? Number(o.hours).toFixed(2) : "–"}</td>
				<td>${o.outside ? `<span class="pill red">${o.outside} outside</span>` : o.punches ? `<span class="pill green">inside</span>` : ""} <span class="muted">${kmTxt(o.max_dist)}</span></td></tr>`;
		});
		h += `</tbody></table>`;
	}
	const sm = salaryMonth((S.hrSet || {}).start_day, r[1], 0);
	h += `<div class="bar"><button class="btn" data-act="hr-mark" data-f="${r[0]}" data-t="${r[1]}" title="Make Attendance records from the punches">Mark staff attendance from punches (${period})</button>
		<button class="btn" data-act="hr-payroll" data-f="${sm[0]}" data-t="${sm[1]}">Run payroll for ${dt(sm[0])} – ${dt(sm[1])}</button></div>
		<div class="muted small">Full day = ${S.hrSet.full_hours || 8} h or more between first IN and last OUT, half day = ${S.hrSet.half_hours || 4} h or more. Days that already have attendance are left alone.</div></div>`;
	// site labour
	if (sites.length) {
		h += `<div class="box"><h3>Site labour ${period} <span class="muted">click a site to see who came</span></h3><table><thead><tr><th>Site</th>
			${one ? "" : `<th class="r">Workers</th>`}<th class="r">${one ? "Present" : "Labour-days"}</th><th class="r">Outside geofence</th><th class="r">Wages</th></tr></thead><tbody>`;
		sites.forEach((s) => {
			h += `<tr class="click" data-act="hr-site" data-p="${esc(s.project || "")}"><td>${esc(pLabel(findProject(s.project || "")))}<div class="muted">${esc(s.project || "No site")}</div></td>
				${one ? "" : `<td class="r">${s.labour || 0}</td>`}<td class="r"><b>${s.present}</b></td><td class="r ${s.outside ? "neg" : ""}">${s.outside || 0}</td><td class="r">${money(s.wage)}</td></tr>`;
		});
		h += `</tbody></table></div>`;
	} else {
		h += `<div class="hint">No site labour punched in for ${period}.</div>`;
	}
	h += `<div class="qa">${[["ext:/sbi_office", "SBI Office punch app"], ["list:Employee Checkin", "Office punches"], ["list:Labour", "Labour register"], ["list:Labour Attendance Log", "Labour punches"],
		["list:Employee", "Employees"], ["list:Attendance", "Staff attendance"], ["list:Salary Slip", "Salary slips"]]
		.map((x) => `<a class="qa-i" data-go="${x[0]}" data-m="hr">${esc(x[1])}</a>`).join("")}</div>`;
	showView(h);
}

async function viewHrSite(projectName) {
	const p = findProject(projectName);
	const r = hrRange();
	const one = r[0] === r[1];
	S.here = () => viewHrSite(projectName);
	setMenu("hr");
	crumbs([["HR", () => viewHr()], ["Attendance", () => viewHr()], [pLabel(p), null]]);
	loading();
	const d = await call("hr_site", { project: projectName, from_date: r[0], to_date: r[1] });
	let h = `<h2 class="t">${esc(pLabel(p))} — ${one ? dt(r[0]) : dt(r[0]) + " – " + dt(r[1])}</h2><div class="sub">${(d.rows || []).length} labour punched.</div>
		<div class="box"><table><thead><tr><th>Labour</th><th>Skill</th>${one ? "" : `<th class="r">Days</th>`}<th>First in</th><th>Last punch</th><th class="r">Punches</th>
		<th>Checked by</th><th>Geofence</th><th class="r">${one ? "Daily wage" : "Wages"}</th></tr></thead><tbody>`;
	(d.rows || []).forEach((x) => {
		h += `<tr class="click" data-act="open" data-dt="Labour" data-name="${esc(x.labour)}"><td><b>${esc(x.labour_name || x.labour)}</b><div class="muted">${esc(x.labour)}</div></td>
			<td>${esc(x.skill)}</td>${one ? "" : `<td class="r"><b>${x.days}</b></td>`}<td>${one ? hm(x.first_in) : dt(x.first_in) + " " + hm(x.first_in)}</td><td>${one ? hm(x.last_punch) : dt(x.last_punch) + " " + hm(x.last_punch)} <span class="muted">${esc(x.last_type)}</span></td><td class="r">${x.punches}</td>
			<td>${esc(x.method)}</td><td>${x.in_fence ? `<span class="pill green">inside</span>` : `<span class="pill red">outside</span>`}</td><td class="r">${money((x.wage || 0) * (one ? 1 : x.days || 0))}</td></tr>`;
	});
	h += `</tbody></table></div>`;
	showView(h);
}

async function viewHrEmp(emp) {
	const r = hrRange();
	S.here = () => viewHrEmp(emp);
	setMenu("hr");
	loading();
	const d = await call("hr_office", { employee: emp, from_date: r[0], to_date: r[1] });
	const e = d.employee || { name: emp };
	crumbs([["HR", () => viewHr()], ["Attendance", () => viewHr()], [e.employee_name || emp, null]]);
	const att = {};
	(d.attendance || []).forEach((a) => (att[String(a.attendance_date)] = a));
	const byDay = {};
	(d.punches || []).forEach((x) => { const k = String(x.time).slice(0, 10); (byDay[k] = byDay[k] || []).push(x); });
	const daysList = Object.keys(byDay).sort();
	let h = `<h2 class="t">${esc(e.employee_name || emp)} <span class="muted">${esc(e.designation || "")}</span></h2>
		<div class="sub">${dt(r[0])}${r[0] !== r[1] ? " – " + dt(r[1]) : ""} · ${daysList.length} day(s) with punches · <a data-act="open" data-dt="Employee" data-name="${esc(emp)}">open employee</a></div>`;
	if (!daysList.length) h += `<div class="hint">No punches in this period.</div>`;
	daysList.forEach((k) => {
		const L = byDay[k];
		const fi = L.find((x) => x.log_type === "IN");
		const lo = [...L].reverse().find((x) => x.log_type === "OUT");
		const hrs = fi && lo && lo.time > fi.time ? ((new Date(String(lo.time).replace(" ", "T")) - new Date(String(fi.time).replace(" ", "T"))) / 3600000) : 0;
		const a = att[k];
		h += `<div class="box"><h3>${dt(k)} <span class="muted">${hrs ? hrs.toFixed(2) + " h" : lo ? "" : "no OUT punch"}</span>
			${a ? `<span class="pill ${a.status === "Present" ? "green" : a.status === "Absent" ? "red" : "orange"}">${esc(a.status)}${a.docstatus === 0 ? " (draft)" : ""}</span>` : `<span class="pill">attendance not marked</span>`}</h3>
			<table><thead><tr><th>Punch</th><th>Time</th><th>Distance</th><th>GPS</th><th>Photo</th><th>Note</th></tr></thead><tbody>
			${L.map((x) => `<tr><td><span class="pill ${x.log_type === "IN" ? "green" : "red"}">${esc(x.log_type)}</span></td><td><b>${hm(x.time)}</b></td>
				<td>${x.distance ? kmTxt(x.distance) : "–"} ${x.within === 0 ? `<span class="pill red">outside</span>` : ""}</td>
				<td>${x.address ? `<div>${esc(x.address)}</div>` : ""}${x.latitude ? `<a href="https://maps.google.com/?q=${x.latitude},${x.longitude}" target="_blank">map</a> <span class="muted">±${Math.round(x.accuracy || 0)} m</span>` : (x.address ? "" : "–")}</td>
				<td>${x.photo ? `<a href="${esc(x.photo)}" target="_blank"><img class="thumb" src="${esc(x.photo)}" alt=""></a>` : "–"}</td><td class="muted">${esc(x.remarks || "")}</td></tr>`).join("")}
			</tbody></table></div>`;
	});
	showView(h);
}

async function viewHrSettings() {
	S.here = viewHrSettings;
	setMenu("hr");
	crumbs([["HR", () => viewHr()], ["Month & office settings", null]]);
	loading();
	const d = await call("hr", { from_date: frappe.datetime.get_today(), to_date: frappe.datetime.get_today() });
	const s = d.settings || {};
	S.hrSet = s;
	const sd = Number(s.start_day) || 1;
	const ex = salaryMonth(sd, frappe.datetime.get_today(), 0);
	showView(`<h2 class="t">Salary month &amp; office settings</h2>
		<div class="sub">Used for “This salary month” on the attendance page, for marking staff attendance from punches, and for the office punch area.</div>
		<div class="fm"><div class="t"><span class="num">1</span> Salary month</div><div class="g g4">
			<label>Month starts on day<input type="number" id="hs-start" min="1" max="28" value="${sd}"></label>
			<label>Month ends on<input id="hs-end" disabled value="${sd === 1 ? "last day of the month" : "day " + (sd - 1) + " of next month"}"></label>
			<label>Full day (hours)<input type="number" id="hs-full" min="1" step="0.5" value="${s.full_hours || 8}"></label>
			<label>Half day (hours)<input type="number" id="hs-half" min="0.5" step="0.5" value="${s.half_hours || 4}"></label></div>
			<div class="muted small" id="hs-ex">This salary month: ${dt(ex[0])} – ${dt(ex[1])}. Use 1 for the calendar month (1st to last day), or for example 26 for 26th to 25th.</div></div>
		<div class="fm"><div class="t"><span class="num">2</span> Office location (for office staff punch)</div><div class="g g4">
			<label>Office name<input id="hs-oname" value="${esc(s.office_name || "")}" placeholder="e.g. Head office, Chennai"></label>
			<label>Latitude<input id="hs-lat" type="number" step="any" value="${s.office_lat || ""}"></label>
			<label>Longitude<input id="hs-lng" type="number" step="any" value="${s.office_lng || ""}"></label>
			<label>Allowed area (metres)<input id="hs-rad" type="number" min="20" step="10" value="${s.office_radius || 200}"></label></div>
			<div class="bar"><button class="btn sm" data-act="hs-here">📍 Use my current location</button>
			${s.office_lat ? `<a class="muted" href="https://maps.google.com/?q=${s.office_lat},${s.office_lng}" target="_blank">See on map ↗</a>` : ""}
			<span class="muted" id="hs-gps"></span></div>
			<div class="muted small">Stand inside the office when you press “Use my current location”.</div></div>
		<div class="fm"><div class="t"><span class="num">3</span> Office time, punch rules and reminders</div><div class="g g4">
			<label>Office starts at<input id="hs-in" type="time" value="${esc(s.in_time || "09:30")}"></label>
			<label>Office ends at<input id="hs-out" type="time" value="${esc(s.out_time || "18:30")}"></label>
			<label>Late after (minutes of grace)<input id="hs-grace" type="number" min="0" max="240" value="${s.late_grace === undefined ? 10 : s.late_grace}"></label>
			<label>Reminder before (minutes)<input id="hs-rem" type="number" min="0" max="120" value="${s.reminder === undefined ? 15 : s.reminder}"></label></div>
			<label class="chk"><input type="checkbox" id="hs-block" ${Number(s.block_outside) !== 0 ? "checked" : ""}> Allow punch only inside the office area (GPS limit above)</label>
			<div class="muted small">Staff get a reminder ${"<b>"}before office starts and before it ends${"</b>"} if they have not punched yet. Field staff who work outside: tick “Can punch anywhere (SBI Office)” on their Employee record.</div></div>
		<div class="bar"><button class="btn pri big" data-act="hs-save">Save settings</button><button class="btn" data-act="hr-back">Back</button></div>`);
}
function hsExample() {
	const sd = Math.min(28, Math.max(1, Number((q("#hs-start") || {}).value) || 1));
	const ex = salaryMonth(sd, frappe.datetime.get_today(), 0);
	if (q("#hs-end")) q("#hs-end").value = sd === 1 ? "last day of the month" : "day " + (sd - 1) + " of next month";
	if (q("#hs-ex")) q("#hs-ex").innerHTML = `This salary month: ${dt(ex[0])} – ${dt(ex[1])}. Use 1 for the calendar month (1st to last day), or for example 26 for 26th to 25th.`;
}
async function hsSave(btn) {
	btn.disabled = true;
	try {
		await call("hr_settings_save", { start_day: q("#hs-start").value, full_hours: q("#hs-full").value, half_hours: q("#hs-half").value,
			office_name: q("#hs-oname").value, office_lat: q("#hs-lat").value, office_lng: q("#hs-lng").value, office_radius: q("#hs-rad").value,
			in_time: q("#hs-in").value, out_time: q("#hs-out").value, late_grace: q("#hs-grace").value, reminder: q("#hs-rem").value,
			block_outside: q("#hs-block").checked ? 1 : 0 });
		S.hrSet = null;
		frappe.show_alert({ message: __("Settings saved"), indicator: "green" }, 4);
		viewHr();
	} catch (e) { btn.disabled = false; }
}
function hsHere() {
	const el = q("#hs-gps");
	if (!navigator.geolocation) { el.textContent = "No GPS in this browser."; return; }
	el.textContent = "Getting location…";
	navigator.geolocation.getCurrentPosition((p) => {
		q("#hs-lat").value = p.coords.latitude.toFixed(7);
		q("#hs-lng").value = p.coords.longitude.toFixed(7);
		el.textContent = "Location filled (±" + Math.round(p.coords.accuracy) + " m). Click Save settings.";
	}, (e) => { el.textContent = "Could not get location: " + e.message; }, { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 });
}
async function hrMark(el) {
	const f = el.dataset.f, t = el.dataset.t;
	frappe.confirm(__("Make staff Attendance from office punches for {0} to {1}? Days that already have attendance are skipped.", [dt(f), dt(t)]), async () => {
		frappe.dom.freeze(__("Marking attendance…"));
		try {
			const r = await call("hr_mark_att", { from_date: f, to_date: t });
			frappe.dom.unfreeze();
			frappe.msgprint({ title: __("Attendance marked"), indicator: r.errors && r.errors.length ? "orange" : "green",
				message: `<b>${r.made}</b> made (present ${r.present}, half day ${r.half}). Already marked: ${r.skipped}. No OUT punch: ${r.no_out}. Too short: ${r.short}.`
					+ (r.errors && r.errors.length ? `<br><br>Could not mark:<br>${r.errors.map(esc).join("<br>")}` : "") });
			viewHr();
		} catch (e) { frappe.dom.unfreeze(); }
	});
}

// ------------------------------------------------------------------ MY WORK (every employee) + HR employees / approvals
const ATT_REASON_HINT = {
	"Work From Home": "Worked from home all day",
	"On Duty": "Worked outside the office for the company (site, client, bank…)",
	"Forgot to Punch": "Came to office but missed the punch",
	"Client / Site Visit": "At a client or site the whole day",
	"Official Travel": "Travelling for company work",
	"Training / Meeting Outside": "Training, meeting or exam outside the office",
	"Mobile / GPS Problem": "Phone, camera or GPS did not work",
	"Other": "Write the reason below",
};
const reqPill = (r) => {
	if (r.docstatus === 1) return `<span class="pill green">Approved</span>`;
	if ((r.sbi_status || r.status) === "Rejected") return `<span class="pill red">Rejected</span>`;
	if (r.status === "Approved") return `<span class="pill green">Approved</span>`;
	return `<span class="pill orange">Waiting for HR</span>`;
};
function fileToJpeg(file, max) {
	return new Promise((ok, bad) => {
		const rd = new FileReader();
		rd.onerror = () => bad(new Error("Could not read the photo"));
		rd.onload = () => {
			const img = new Image();
			img.onerror = () => bad(new Error("This file is not a photo"));
			img.onload = () => {
				const k = Math.min(1, (max || 900) / Math.max(img.width, img.height));
				const c = document.createElement("canvas");
				c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
				c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
				ok(c.toDataURL("image/jpeg", 0.85));
			};
			img.src = rd.result;
		};
		rd.readAsDataURL(file);
	});
}
const val = (s) => ((q(s) || {}).value || "").trim();
const avatar = (img, name, cls) => img ? `<img class="av ${cls || ""}" src="${esc(img)}" alt="">`
	: `<span class="av ${cls || ""}">${esc(String(name || "?").trim().slice(0, 1).toUpperCase())}</span>`;

// one month of attendance for an employee (used by "My attendance" and by HR)
function monthHtml(d, hr) {
	const e = d.employee || {};
	const sm = d.summary || {};
	const hol = {};
	(d.holidays || []).forEach((x) => (hol[x.d] = x.description || "Holiday"));
	const lb = d.leave_balance || [];
	const back = Number(S.mBack || 0);
	let h = `<div class="emp-head">${avatar(e.image, e.employee_name, "big")}<div><h2 class="t">${esc(e.employee_name || "")}</h2>
		<div class="sub">${esc([e.employee_number ? "ID " + e.employee_number : "", e.designation, e.department].filter(Boolean).join(" · "))}</div></div>
		<div class="emp-mon"><button class="btn sm" data-act="m-back" data-b="${back + 1}">‹</button><b>${dt(d.from_date)} – ${dt(d.to_date)}</b>
		<button class="btn sm" data-act="m-back" data-b="${Math.max(0, back - 1)}" ${back ? "" : "disabled"}>›</button></div></div>
		<div class="tiles">
			<div class="tile"><div class="l">Days present</div><div class="v">${sm.present || 0}</div><div class="s">punched or marked present</div></div>
			<div class="tile"><div class="l">Hours worked</div><div class="v">${Number(sm.hours || 0).toFixed(1)}</div><div class="s">first IN to last OUT</div></div>
			<div class="tile"><div class="l">Late days</div><div class="v ${sm.late ? "neg" : ""}">${sm.late || 0}</div><div class="s">after start time + grace</div></div>
			<div class="tile"><div class="l">Leave left</div><div class="v">${lb.reduce((a, x) => a + Number(x.left || 0), 0)}</div>
				<div class="s">${lb.length ? lb.map((x) => esc(x.leave_type) + " " + Number(x.left)).join(" · ") : "no leave allocated"}</div></div>
		</div>`;
	if (!hr) h += `<div class="bar"><a class="btn pri" href="/sbi_office">${ICON("clock")} Punch IN / OUT</a>
		<button class="btn" data-go="me-att" data-m="me">Attendance request</button><button class="btn" data-go="me-leave" data-m="me">Leave request</button></div>`;
	if (hr && e.sbi_face_front) h += `<div class="box"><h3>Face record <span class="muted">taken in SBI Office at the first punch</span></h3><div class="faces">
		${["sbi_face_front", "sbi_face_left", "sbi_face_right"].map((k) => e[k] ? `<a href="${esc(e[k])}" target="_blank"><img src="${esc(e[k])}" alt=""></a>` : "").join("")}</div></div>`;
	// day by day
	h += `<div class="box"><h3>Day by day <span class="muted">tap a day to see each punch with photo and place</span></h3>`;
	const days = d.days || [];
	if (!days.length) h += `<div class="hint">No punches or attendance in this month yet.</div>`;
	else {
		h += `<table class="mday"><thead><tr><th>Date</th><th>In</th><th>Out</th><th class="r">Hours</th><th>Status</th></tr></thead><tbody>`;
		days.forEach((x, i) => {
			const st = x.att ? `<span class="pill ${/Present|Work/.test(x.att) ? "green" : /Absent/.test(x.att) ? "red" : "orange"}">${esc(x.att)}</span>`
				: x.first_in ? (x.last_out ? `<span class="pill">punched</span>` : `<span class="pill orange">no OUT</span>`) : "";
			h += `<tr class="click" data-act="m-day" data-i="${i}"><td><b>${dt(x.d)}</b> <span class="muted">${esc(frappe.datetime.str_to_obj(x.d).toLocaleDateString("en-IN", { weekday: "short" }))}</span>
				${hol[x.d] ? `<div class="muted">${esc(hol[x.d])}</div>` : ""}</td>
				<td>${esc(x.first_in || "–")}${x.late ? ` <span class="pill orange">late</span>` : ""}</td><td>${esc(x.last_out || "–")}</td>
				<td class="r">${x.hours ? Number(x.hours).toFixed(2) : "–"}</td><td>${st}${x.outside ? ` <span class="pill red">${x.outside} outside</span>` : ""}</td></tr>
				<tr class="mpun hide" data-day="${i}"><td colspan="5">${(x.punches || []).map((p) => `<div class="pun">
					${p.photo ? `<a href="${esc(p.photo)}" target="_blank"><img src="${esc(p.photo)}" alt=""></a>` : `<span class="nophoto">no photo</span>`}
					<div><span class="pill ${p.log_type === "IN" ? "green" : "red"}">${esc(p.log_type)}</span> <b>${esc(p.t)}</b>
					${p.distance ? ` <span class="muted">${kmTxt(p.distance)} from office</span>` : ""}${p.within === 0 ? ` <span class="pill red">outside</span>` : ""}
					<div class="muted">${esc(p.address || "")}</div>
					${p.latitude ? `<a href="https://maps.google.com/?q=${p.latitude},${p.longitude}" target="_blank">See on map ↗</a> <span class="muted">±${Math.round(p.accuracy || 0)} m</span>` : ""}
					${p.remarks ? `<div class="muted">Reason: ${esc(p.remarks)}</div>` : ""}</div></div>`).join("") || `<span class="muted">No punches – ${esc(x.att || "")}</span>`}</td></tr>`;
		});
		h += `</tbody></table>`;
	}
	h += `</div>`;
	h += reqTables(d, !hr);
	if ((d.slips || []).length) {
		h += `<div class="box"><h3>Salary slips</h3><table><thead><tr><th>Month</th><th class="r">Net pay</th><th></th></tr></thead><tbody>
			${d.slips.map((s) => `<tr><td>${dt(s.start_date)} – ${dt(s.end_date)}</td><td class="r"><b>${money(s.net_pay)}</b></td>
				<td class="r"><a href="/printview?doctype=Salary%20Slip&name=${encodeURIComponent(s.name)}&trigger_print=0" target="_blank">View / print ↗</a></td></tr>`).join("")}</tbody></table></div>`;
	}
	return h;
}
function attTable(ar, mine) {
	let h = `<div class="box"><h3>Attendance requests ${mine ? `<a class="muted" data-go="me-att" data-m="me">+ New request</a>` : ""}</h3>`;
	h += ar.length ? `<table><thead><tr><th>Dates</th><th>Reason</th><th>Status</th>${mine ? "<th></th>" : ""}</tr></thead><tbody>${ar.map((r) => `<tr>
		<td>${dt(r.from_date)}${String(r.to_date) !== String(r.from_date) ? " – " + dt(r.to_date) : ""}${r.half_day ? " <span class='muted'>(half day)</span>" : ""}</td>
		<td><b>${esc(r.reason)}</b><div class="muted">${esc(r.explanation)}</div>${r.hr_remarks ? `<div class="muted">HR: ${esc(r.hr_remarks)}</div>` : ""}</td><td>${reqPill(r)}</td>
		${mine ? `<td class="r">${r.docstatus === 0 && r.sbi_status !== "Rejected" ? `<a data-act="me-withdraw" data-k="att" data-n="${esc(r.name)}">Withdraw</a>` : ""}</td>` : ""}</tr>`).join("")}</tbody></table>`
		: `<div class="hint">No attendance requests.</div>`;
	return h + `</div>`;
}
function leaveTable(lv, mine) {
	let h = `<div class="box"><h3>Leave requests ${mine ? `<a class="muted" data-go="me-leave" data-m="me">+ New leave</a>` : ""}</h3>`;
	h += lv.length ? `<table><thead><tr><th>Dates</th><th>Leave</th><th class="r">Days</th><th>Status</th>${mine ? "<th></th>" : ""}</tr></thead><tbody>${lv.map((r) => `<tr>
		<td>${dt(r.from_date)}${String(r.to_date) !== String(r.from_date) ? " – " + dt(r.to_date) : ""}</td><td><b>${esc(r.leave_type)}</b><div class="muted">${esc(r.description)}</div></td>
		<td class="r">${Number(r.total_leave_days || 0)}</td><td>${reqPill(r)}</td>
		${mine ? `<td class="r">${r.docstatus === 0 && r.status === "Open" ? `<a data-act="me-withdraw" data-k="leave" data-n="${esc(r.name)}">Withdraw</a>` : ""}</td>` : ""}</tr>`).join("")}</tbody></table>`
		: `<div class="hint">No leave requests.</div>`;
	return h + `</div>`;
}
function reqTables(d, mine) {
	let h = attTable(d.att_requests || [], mine) + leaveTable(d.leaves || [], mine);
	const ch = d.changes || [];
	if (ch.length) h += `<div class="box"><h3>Changes to details</h3><table><tbody>${ch.map((c) => `<tr><td>${dt(c.creation)}</td><td>${esc(c.summary)}${c.hr_remarks ? `<div class="muted">HR: ${esc(c.hr_remarks)}</div>` : ""}</td>
		<td>${c.status === "Pending" ? `<span class="pill orange">Waiting for HR</span>` : c.status === "Approved" ? `<span class="pill green">Approved</span>` : `<span class="pill red">Rejected</span>`}</td>
		${mine ? `<td class="r">${c.status === "Pending" ? `<a data-act="me-withdraw" data-k="change" data-n="${esc(c.name)}">Withdraw</a>` : ""}</td>` : ""}</tr>`).join("")}</tbody></table></div>`;
	return h;
}

async function viewMe() {
	S.here = viewMe; S.current = viewMe;
	setMenu("me");
	crumbs([["My work", null], ["My attendance", null]]);
	loading();
	S.mData = await call("me_home", { back: S.mBack || 0 });
	showView(monthHtml(S.mData, false));
}
async function meData() {
	if (!S.mData) S.mData = await call("me_home", { back: 0 });
	return S.mData;
}
async function viewMeAtt() {
	S.here = viewMeAtt; S.current = viewMeAtt;
	setMenu("me");
	crumbs([["My work", () => go("me", "me")], ["Attendance request", null]]);
	loading();
	S.mBack = 0; S.mData = null;
	const d = await meData();
	const reasons = d.att_reasons || ["Work From Home", "On Duty"];
	const today = frappe.datetime.get_today();
	showView(`<h2 class="t">Attendance request</h2>
		<div class="sub">Use this when you could not punch in SBI Office – HR will check and approve. Approved days count as present.</div>
		<div class="fm"><div class="t"><span class="num">1</span> Which day(s)</div><div class="g g4">
			<label>From<input type="date" id="ar-from" value="${today}" max="${frappe.datetime.add_days(today, 30)}"></label>
			<label>To<input type="date" id="ar-to" value="${today}"></label>
			<label class="chk"><input type="checkbox" id="ar-half"> Half day only</label></div></div>
		<div class="fm"><div class="t"><span class="num">2</span> Why</div><div class="opts">${reasons.map((r, i) => `<label class="opt"><input type="radio" name="ar-reason" value="${esc(r)}" ${i === 0 ? "checked" : ""}>
			<b>${esc(r)}</b><span>${esc(ATT_REASON_HINT[r] || "")}</span></label>`).join("")}</div>
			<label>Details (where you were, what work)<textarea id="ar-exp" rows="3" placeholder="e.g. At Velachery site for slab casting with the site engineer"></textarea></label></div>
		<div class="bar"><button class="btn pri big" data-act="ar-save">Send to HR</button></div>
		${attTable(d.att_requests || [], true)}`);
}
async function viewMeLeave() {
	S.here = viewMeLeave; S.current = viewMeLeave;
	setMenu("me");
	crumbs([["My work", () => go("me", "me")], ["Leave request", null]]);
	loading();
	S.mBack = 0; S.mData = null;
	const d = await meData();
	const lb = d.leave_balance || [];
	const types = d.leave_types || [];
	const today = frappe.datetime.get_today();
	showView(`<h2 class="t">Leave request</h2>
		<div class="sub">HR approves your leave. You can withdraw it until it is approved.</div>
		${lb.length ? `<div class="tiles">${lb.map((x) => `<div class="tile"><div class="l">${esc(x.leave_type)}</div><div class="v">${Number(x.left)}</div><div class="s">of ${Number(x.allocated)} · used ${Number(x.used)}</div></div>`).join("")}</div>`
			: `<div class="hint">HR has not given you leave for this year yet. You can still ask for Leave Without Pay.</div>`}
		<div class="fm"><div class="g g4">
			<label>Leave type<select id="lv-type">${types.map((t) => `<option ${lb.length && lb[0].leave_type === t ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></label>
			<label>From<input type="date" id="lv-from" value="${today}"></label>
			<label>To<input type="date" id="lv-to" value="${today}"></label>
			<label class="chk"><input type="checkbox" id="lv-half"> Half day</label></div>
			<label>Reason<textarea id="lv-desc" rows="2" placeholder="e.g. Family function at native place"></textarea></label></div>
		<div class="bar"><button class="btn pri big" data-act="lv-save">Send to HR</button></div>
		${leaveTable(d.leaves || [], true)}`);
}
async function viewMeProfile() {
	S.here = viewMeProfile; S.current = viewMeProfile;
	setMenu("me");
	crumbs([["My work", () => go("me", "me")], ["My details", null]]);
	loading();
	const d = await call("me_profile");
	const e = d.employee || {};
	S.meNewPhoto = "";
	const inp = (f) => {
		const v = e[f.fieldname] === null || e[f.fieldname] === undefined ? "" : String(e[f.fieldname]);
		if (f.fieldtype === "Select") return `<select data-f="${f.fieldname}"><option></option>${String(f.options).split("\n").filter(Boolean).map((o) => `<option ${o === v ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>`;
		if (f.fieldtype === "Date") return `<input type="date" data-f="${f.fieldname}" value="${esc(v)}">`;
		if (/Text/.test(f.fieldtype)) return `<textarea data-f="${f.fieldname}" rows="2">${esc(v)}</textarea>`;
		return `<input data-f="${f.fieldname}" value="${esc(v)}">`;
	};
	showView(`<div class="emp-head">${avatar(e.image, e.employee_name, "big")}<div><h2 class="t">My details</h2>
		<div class="sub">${esc([e.employee_name, e.employee_number ? "ID " + e.employee_number : "", e.designation].filter(Boolean).join(" · "))}</div></div></div>
		${d.pending ? `<div class="warn">You already sent changes that HR has not checked yet. A new change is sent as another request.</div>` : ""}
		<div class="sub">Change what is wrong and press <b>Send to HR</b>. Your details change only after HR approves.</div>
		<div class="fm"><div class="t">Photo</div><div class="bar"><label class="btn">${ICON("upload")} Choose new photo<input type="file" id="me-photo" accept="image/*" class="hide"></label>
			<img id="me-photo-prev" class="av big hide" alt=""></div></div>
		<div class="fm"><div class="g g3">${(d.fields || []).map((f) => `<label>${esc(f.label)}${inp(f)}</label>`).join("")}</div></div>
		<div class="bar"><button class="btn pri big" data-act="me-prof-save">Send to HR</button></div>`);
	S.meOrig = {};
	R.querySelectorAll("[data-f]").forEach((x) => (S.meOrig[x.dataset.f] = x.value));
}
function viewMeSlips() {
	S.mBack = 0;
	viewMe().then(() => { const b = R.querySelectorAll("#view .box h3"); b.forEach((h) => { if (/Salary slips/.test(h.textContent)) h.scrollIntoView({ behavior: "smooth" }); }); });
}
function viewChangePw(first) {
	S.here = () => viewChangePw(first);
	if (!first) { setMenu("me"); crumbs([["My work", () => go("me", "me")], ["Change password", null]]); }
	const html = `<div class="pw-box"><h2 class="t">${first ? "Welcome! Set your own password" : "Change password"}</h2>
		<div class="sub">${first ? "You logged in with the default password. Choose a new one that only you know. After saving you will log in again with your user id and the new password." : "After saving you will log in again with the new password."}</div>
		<div class="fm"><label>New password<input type="password" id="pw1" autocomplete="new-password" placeholder="at least 8 letters and numbers"></label>
		<label>Type it again<input type="password" id="pw2" autocomplete="new-password"></label>
		<label class="chk"><input type="checkbox" id="pw-show"> Show password</label></div>
		<div class="bar"><button class="btn pri big" data-act="pw-save">Save new password</button></div>
		<div class="muted small">Use letters and numbers, for example Ravi@4521. Do not use SBI@2026 again.</div></div>`;
	if (first) {
		q("#lx").insertAdjacentHTML("beforeend", `<div class="pw-cover" id="pw-cover">${html}</div>`);
	} else showView(html);
}
async function pwSave(btn) {
	const a = (q("#pw1") || {}).value || "", b = (q("#pw2") || {}).value || "";
	if (a.length < 8) { frappe.msgprint(__("The new password must have at least 8 letters / numbers.")); return; }
	if (a !== b) { frappe.msgprint(__("The two passwords are not the same.")); return; }
	btn.disabled = true;
	try {
		await call("set_password", { new_password: a });
		frappe.msgprint({ title: __("Password changed"), indicator: "green", message: __("Please log in again with your user id and the new password.") });
		setTimeout(() => {
			frappe.call({ method: "logout" }).always(() => { window.location.href = "/login"; });
		}, 1800);
	} catch (e) { btn.disabled = false; }
}

// ---- HR: dashboard, employees, requests, letters
async function viewHrDash() {
	S.here = viewHrDash; S.current = viewHrDash;
	setMenu("hr");
	crumbs([["HR", null], ["HR dashboard", null]]);
	loading();
	const d = await call("emp_list", { q: "" });
	S.emps = d.employees || [];
	const act = S.emps.filter((e) => e.status === "Active");
	const punched = act.filter((e) => e.first_in || e.last_type);
	const inNow = act.filter((e) => e.last_type === "IN");
	const late = act.filter((e) => e.late);
	const onLeave = act.filter((e) => e.leave);
	const notYet = act.filter((e) => !e.first_in && !e.last_type && !e.leave);
	const p = d.pending || {};
	const pend = (p.att || 0) + (p.leave || 0) + (p.change || 0);
	let h = `<h2 class="t">HR dashboard <span class="muted">${dt(frappe.datetime.get_today())}</span></h2>
		<div class="tiles">
			<div class="tile go" data-act="hd-filter" data-f="all"><div class="l">Total employees</div><div class="v">${act.length}</div><div class="s">active · ${S.emps.length - act.length} left</div></div>
			<div class="tile go" data-act="hd-filter" data-f="present"><div class="l">Present today</div><div class="v">${punched.length}</div><div class="s">in office now ${inNow.length}</div></div>
			<div class="tile go" data-act="hd-filter" data-f="late"><div class="l">Late today</div><div class="v ${late.length ? "neg" : ""}">${late.length}</div></div>
			<div class="tile go" data-act="hd-filter" data-f="leave"><div class="l">On leave / request</div><div class="v">${onLeave.length}</div></div>
			<div class="tile go" data-act="hd-filter" data-f="absent"><div class="l">Not punched yet</div><div class="v ${notYet.length ? "neg" : ""}">${notYet.length}</div></div>
			<div class="tile go" data-go="hr-req" data-m="hr"><div class="l">Requests to approve</div><div class="v ${pend ? "neg" : ""}">${pend}</div>
				<div class="s">attendance ${p.att || 0} · leave ${p.leave || 0} · details ${p.change || 0}</div></div>
		</div>
		<div class="bar"><input id="hd-q" placeholder="Search name, ID No. or phone" style="max-width:280px">
			<button class="btn pri" data-act="emp-new">${ICON("plus")} Add employee</button><button class="btn" data-go="hr" data-m="hr">Attendance (day / month)</button>
			<button class="btn" data-go="report:Monthly Attendance Sheet" data-m="hr">Attendance report</button></div>
		<div class="box"><h3>Employees today <span class="muted" id="hd-lbl">all</span> <span class="muted">· tap a name for the month: punches with photo &amp; GPS, leave, requests</span></h3><div id="hd-list"></div></div>`;
	showView(h);
	S.hdFilter = "all";
	hdList();
}
function hdList() {
	const f = S.hdFilter || "all";
	const qq = ((q("#hd-q") || {}).value || "").toLowerCase();
	const L = (S.emps || []).filter((e) => {
		if (qq && (e.employee_name + " " + e.employee_number + " " + e.cell_number + " " + e.name).toLowerCase().indexOf(qq) < 0) return false;
		if (f === "all") return e.status === "Active" || qq;
		if (e.status !== "Active") return false;
		if (f === "present") return e.first_in || e.last_type;
		if (f === "late") return e.late;
		if (f === "leave") return e.leave;
		if (f === "absent") return !e.first_in && !e.last_type && !e.leave;
		return true;
	});
	const lbl = { all: "all", present: "present today", late: "late today", leave: "on leave", absent: "not punched yet" };
	if (q("#hd-lbl")) q("#hd-lbl").textContent = lbl[f] + " (" + L.length + ")";
	q("#hd-list").innerHTML = L.length ? `<table><thead><tr><th>Employee</th><th>ID No.</th><th>In</th><th>Out</th><th>Today</th><th>Login</th><th></th></tr></thead><tbody>
		${L.map((e) => `<tr class="click" data-act="emp-month" data-e="${esc(e.name)}"><td><div class="emp-cell">${avatar(e.image, e.employee_name)}<div><b>${esc(e.employee_name)}</b>
			<div class="muted">${esc(e.designation || "")}${e.status !== "Active" ? " · " + esc(e.status) : ""}</div></div></div></td>
			<td>${esc(e.employee_number || "–")}</td><td>${esc(e.first_in || "–")}${e.late ? ` <span class="pill orange">late</span>` : ""}</td><td>${esc(e.last_out || "–")}</td>
			<td>${e.leave ? `<span class="pill orange">${esc(e.leave)}</span>` : e.last_type === "IN" ? `<span class="pill green">in office</span>` : e.last_type ? `<span class="pill">left</span>` : `<span class="pill red">not punched</span>`}</td>
			<td>${e.username ? `<span class="muted">${esc(e.username)}</span>` : e.user_id ? `<span class="muted">${esc(e.user_id)}</span>` : `<span class="pill orange">no login</span>`}</td>
			<td class="r"><a data-act="emp-edit" data-e="${esc(e.name)}">Edit</a></td></tr>`).join("")}</tbody></table>` : `<div class="hint">Nobody here.</div>`;
}
async function viewEmpMonth(emp) {
	S.here = () => viewEmpMonth(emp); S.current = S.here;
	setMenu("hr");
	loading();
	const d = await call("emp_month", { employee: emp, back: S.mBack || 0 });
	S.mData = d;
	const e = d.employee || {};
	crumbs([["HR", () => viewHrDash()], ["HR dashboard", () => viewHrDash()], [e.employee_name || emp, null]],
		`<a class="hpill" data-act="emp-edit" data-e="${esc(emp)}">Edit employee</a>`);
	showView(monthHtml(d, true));
}
async function viewEmpForm(name) {
	S.here = () => viewEmpForm(name); S.current = S.here;
	setMenu("hr");
	crumbs([["HR", () => viewHrDash()], ["Employees", () => viewHrDash()], [name ? "Edit employee" : "Add employee", null]]);
	loading();
	const d = await call("emp_get", { employee: name || "" });
	const e = d.employee || {};
	const L = d.login || {};
	S.empPhoto = "";
	const has = (f) => (d.fields || []).indexOf(f) >= 0;
	const v = (f) => esc(e[f] === null || e[f] === undefined ? "" : e[f]);
	const sel = (f, opts, label, req) => has(f) ? `<label>${label}${req ? " *" : ""}<select id="ef-${f}"><option></option>${opts.map((o) => `<option ${String(e[f] || "") === o ? "selected" : ""}>${esc(o)}</option>`).join("")}</select></label>` : "";
	const inp = (f, label, type, req, ph) => has(f) ? `<label>${label}${req ? " *" : ""}<input id="ef-${f}" type="${type || "text"}" value="${v(f)}" placeholder="${esc(ph || "")}"></label>` : "";
	const ta = (f, label) => has(f) ? `<label>${label}<textarea id="ef-${f}" rows="2">${v(f)}</textarea></label>` : "";
	const mods = [["attendance", "Attendance only", "Punch, my attendance, leave and requests (everyone gets this)"], ["hr", "HR", "Employees, attendance, leave, payroll"],
		["sales", "Sales", "Sales orders and invoices"], ["purchase", "Purchase", "Purchase orders and bills"], ["projects", "Projects", "Projects, BOQ, site cash"],
		["accounts", "Accounts", "Full accounts: cash, bank, GST, Tally"]];
	const on = L.modules || [];
	S.empFields = d.fields || [];
	showView(`<div class="emp-head"><label class="ph-pick">${e.image ? `<img id="ef-prev" class="av big" src="${esc(e.image)}" alt="">` : `<img id="ef-prev" class="av big hide" alt=""><span class="av big" id="ef-noph">${ICON("upload")}</span>`}
		<input type="file" id="ef-photo" accept="image/*" class="hide"><span class="muted small">${e.image ? "Change photo" : "Add photo *"}</span></label>
		<div><h2 class="t">${name ? esc(e.employee_name || name) : "Add employee"}</h2><div class="sub">${name ? esc(name) : "Fill the details, add the photo, and give a login if this person will use the app."}</div></div></div>
		<div class="fm"><div class="t"><span class="num">1</span> Employee</div><div class="g g4">
			${inp("employee_number", "Employee ID No.", "text", 1, "e.g. SBI-045")}${inp("first_name", "First name", "text", 1)}${inp("middle_name", "Middle name")}${inp("last_name", "Last name")}
			${sel("gender", d.genders || ["Male", "Female"], "Gender", 1)}${inp("date_of_birth", "Date of birth", "date", 1)}${inp("date_of_joining", "Date of joining", "date", 1)}
			${sel("company", d.companies || [], "Company", 1)}${sel("designation", d.designations || [], "Designation")}${sel("department", d.departments || [], "Department")}
			${inp("cell_number", "Mobile", "tel")}${inp("personal_email", "Personal e-mail", "email")}${sel("status", ["Active", "Inactive", "Suspended", "Left"], "Status")}
			${inp("relieving_date", "Relieving date", "date")}${inp("reason_for_leaving", "Reason for leaving")}</div></div>
		<div class="fm"><div class="t"><span class="num">2</span> Address, contact &amp; bank</div><div class="g g3">
			${ta("current_address", "Current address")}${ta("permanent_address", "Permanent address")}${sel("blood_group", ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"], "Blood group")}
			${inp("person_to_be_contacted", "Emergency contact name")}${inp("emergency_phone_number", "Emergency phone", "tel")}${inp("relation", "Relation")}
			${inp("bank_name", "Bank name")}${inp("bank_ac_no", "Bank A/c No.")}${inp("ifsc_code", "IFSC")}${inp("ctc", "CTC (yearly)", "number")}</div></div>
		<div class="fm"><div class="t"><span class="num">3</span> Login for Lite ERP and SBI Office</div>
			${L.user ? `<div class="hint">Login: <b>${esc(L.username || L.user)}</b> ${L.enabled ? `<span class="pill green">active</span>` : `<span class="pill red">disabled</span>`}
				${L.must_change ? `<span class="pill orange">must change password at next login</span>` : ""}</div>` : ""}
			<label class="chk"><input type="checkbox" id="ef-login" ${L.user ? "checked" : ""}> ${L.user ? "Keep / update the login" : "Give this employee a login"}</label>
			<div id="ef-login-box" class="${L.user ? "" : "hide"}"><div class="g g4"><label>User id * <input id="ef-uname" value="${esc(L.username || "")}" placeholder="e.g. ravi or sbi045" autocapitalize="off"></label>
				<label>Password<input disabled value="${L.user ? "unchanged" : "SBI@2026 (first login only)"}"></label>
				${L.user ? `<label class="chk"><input type="checkbox" id="ef-reset"> Reset password to SBI@2026</label><label class="chk"><input type="checkbox" id="ef-disable"> Disable login</label>` : ""}</div>
				<div class="t" style="margin-top:8px">Allowed areas * <span class="muted small">choose at least one</span></div>
				<div class="opts">${mods.map((m) => `<label class="opt"><input type="checkbox" class="ef-mod" value="${m[0]}" ${m[0] === "attendance" ? "checked disabled" : on.indexOf(m[0]) >= 0 ? "checked" : ""}><b>${m[1]}</b><span>${m[2]}</span></label>`).join("")}</div>
				<div class="muted small">The person logs in with the user id (not e-mail) and SBI@2026, must set a new password, then logs in again. Lite ERP opens by itself.</div></div></div>
		<div class="bar"><button class="btn pri big" data-act="emp-save" data-e="${esc(name || "")}">Save employee</button>
			${name ? `<button class="btn" data-act="letter" data-f="SBI Appointment Order" data-e="${esc(name)}">Appointment order</button>
			<button class="btn" data-act="letter" data-f="SBI Relieving Order" data-e="${esc(name)}">Relieving order</button>
			<button class="btn" data-act="emp-month" data-e="${esc(name)}">Month attendance</button>
			<button class="btn" data-act="open" data-dt="Employee" data-name="${esc(name)}">Full employee form</button>` : ""}</div>`);
}
async function empSave(btn) {
	const name = btn.dataset.e || "";
	const vals = {};
	(S.empFields || []).forEach((f) => { const x = q("#ef-" + f); if (x) vals[f] = x.value.trim(); });
	const login = q("#ef-login") && q("#ef-login").checked;
	const mods = Array.from(R.querySelectorAll(".ef-mod:checked")).map((x) => x.value);
	if (!vals.employee_number) { frappe.msgprint(__("Employee ID No. is needed.")); return; }
	if (!name && !S.empPhoto) { frappe.msgprint(__("Add the employee photo (tap the round picture).")); return; }
	if (login && !val("#ef-uname")) { frappe.msgprint(__("Type the user id for the login.")); return; }
	if (login && !mods.length) { frappe.msgprint(__("Choose at least one allowed area.")); return; }
	btn.disabled = true;
	try {
		const r = await call("emp_save", { employee: name, values: JSON.stringify(vals), photo: S.empPhoto || "",
			create_login: login ? 1 : 0, username: val("#ef-uname"), modules: JSON.stringify(mods),
			reset_password: q("#ef-reset") && q("#ef-reset").checked ? 1 : 0, disable_login: q("#ef-disable") && q("#ef-disable").checked ? 1 : 0 });
		const L = r.login || {};
		frappe.msgprint({ title: __("Employee saved"), indicator: "green", message: `<b>${esc(r.employee)}</b> saved.` +
			(L.password ? `<br><br>Login user id: <b>${esc(L.username)}</b><br>Password: <b>${esc(L.password)}</b><br>Site: ${esc(window.location.origin)}<br>They must set their own password at the first login.` : "") +
			(L.disabled ? "<br>Login disabled." : "") });
		viewEmpForm(r.employee);
	} catch (e) { btn.disabled = false; }
}
async function viewReqs(tab) {
	S.reqTab = tab || S.reqTab || "att";
	S.here = () => viewReqs(); S.current = S.here;
	setMenu("hr");
	crumbs([["HR", () => viewHrDash()], ["Requests to approve", null]]);
	loading();
	const d = await call("req_list");
	const att = d.att || [], lv = d.leave || [], ch = d.change || [];
	const pa = att.filter((r) => r.docstatus === 0 && r.sbi_status !== "Rejected").length;
	const pl = lv.filter((r) => r.docstatus === 0 && r.status === "Open").length;
	const pc = ch.filter((r) => r.status === "Pending").length;
	const tabs = [["att", "Attendance requests", pa], ["leave", "Leave requests", pl], ["change", "Detail changes", pc]];
	let h = `<h2 class="t">Requests to approve</h2><div class="seg">${tabs.map((t) => `<a class="${S.reqTab === t[0] ? "on" : ""}" data-act="req-tab" data-t="${t[0]}">${t[1]}${t[2] ? ` <span class="pill orange">${t[2]}</span>` : ""}</a>`).join("")}</div>`;
	const btns = (k, n, open) => open ? `<div class="req-act"><input class="req-rem" data-n="${esc(n)}" placeholder="Remark (optional)">
		<button class="btn sm pri" data-act="req-do" data-k="${k}" data-n="${esc(n)}" data-do="approve">${ICON("check")} Approve</button>
		<button class="btn sm" data-act="req-do" data-k="${k}" data-n="${esc(n)}" data-do="reject">Reject</button></div>` : "";
	const who = (r) => `<a data-act="emp-month" data-e="${esc(r.employee)}"><b>${esc(r.employee_name || r.employee)}</b></a>`;
	if (S.reqTab === "att") {
		h += att.length ? `<div class="box"><table><thead><tr><th>Employee</th><th>Dates</th><th>Reason</th><th>Status</th><th></th></tr></thead><tbody>${att.map((r) => `<tr>
			<td>${who(r)}<div class="muted">${dt(r.creation)}</div></td><td>${dt(r.from_date)}${r.to_date !== r.from_date ? " – " + dt(r.to_date) : ""}${r.half_day ? " (half)" : ""}</td>
			<td><b>${esc(r.reason)}</b><div class="muted">${esc(r.explanation)}</div>${r.hr_remarks ? `<div class="muted">HR: ${esc(r.hr_remarks)}</div>` : ""}</td><td>${reqPill(r)}</td>
			<td>${btns("att", r.name, r.docstatus === 0 && r.sbi_status !== "Rejected")}</td></tr>`).join("")}</tbody></table></div>` : `<div class="hint">No attendance requests.</div>`;
	} else if (S.reqTab === "leave") {
		h += lv.length ? `<div class="box"><table><thead><tr><th>Employee</th><th>Dates</th><th>Leave</th><th class="r">Days</th><th>Status</th><th></th></tr></thead><tbody>${lv.map((r) => `<tr>
			<td>${who(r)}<div class="muted">${dt(r.creation)}</div></td><td>${dt(r.from_date)}${String(r.to_date) !== String(r.from_date) ? " – " + dt(r.to_date) : ""}</td>
			<td><b>${esc(r.leave_type)}</b><div class="muted">${esc(r.description)}</div></td><td class="r">${Number(r.total_leave_days || 0)}</td><td>${reqPill(r)}</td>
			<td>${btns("leave", r.name, r.docstatus === 0 && r.status === "Open")}</td></tr>`).join("")}</tbody></table></div>` : `<div class="hint">No leave requests.</div>`;
	} else {
		h += ch.length ? ch.map((c) => `<div class="box"><h3>${who(c)} <span class="muted">${dt(c.creation)}</span>
			${c.status === "Pending" ? `<span class="pill orange">Waiting</span>` : c.status === "Approved" ? `<span class="pill green">Approved</span>` : `<span class="pill red">Rejected</span>`}</h3>
			<table><thead><tr><th>Detail</th><th>Now</th><th>New</th></tr></thead><tbody>${(c.items || []).map((x) => `<tr><td>${esc(x.label)}</td><td class="muted">${esc(x.old || "–")}</td><td><b>${esc(x.new || "–")}</b></td></tr>`).join("")}
			${c.new_photo ? `<tr><td>Photo</td><td></td><td><a href="${esc(c.new_photo)}" target="_blank"><img class="thumb" src="${esc(c.new_photo)}" alt=""></a></td></tr>` : ""}</tbody></table>
			${c.hr_remarks ? `<div class="muted">HR: ${esc(c.hr_remarks)}</div>` : ""}${btns("change", c.name, c.status === "Pending")}</div>`).join("") : `<div class="hint">No detail changes.</div>`;
	}
	showView(h);
}
async function reqDo(el) {
	const rem = (R.querySelector(`.req-rem[data-n="${CSS.escape(el.dataset.n)}"]`) || {}).value || "";
	if (el.dataset.do === "reject" && !rem.trim()) { frappe.msgprint(__("Write a remark saying why it is rejected.")); return; }
	el.disabled = true;
	try {
		await call("req_action", { kind: el.dataset.k, name: el.dataset.n, do: el.dataset.do, remarks: rem.trim() });
		frappe.show_alert({ message: el.dataset.do === "approve" ? __("Approved") : __("Rejected"), indicator: el.dataset.do === "approve" ? "green" : "orange" });
		viewReqs();
	} catch (e) { el.disabled = false; }
}
async function pickEmployee(title, next) {
	S.here = () => pickEmployee(title, next);
	setMenu("hr");
	crumbs([["HR", () => viewHrDash()], [title, null]]);
	loading();
	const d = await call("emp_list", { q: "" });
	S.emps = d.employees || [];
	S.onEmp = next;
	showView(`<h2 class="t">${esc(title)}</h2><div class="sub">Pick the employee.</div>
		<div class="bar"><input id="pe-q" placeholder="Search name or ID No." style="max-width:280px"></div><div class="box" id="pe-list"></div>`);
	peList();
}
function peList() {
	const qq = ((q("#pe-q") || {}).value || "").toLowerCase();
	const L = (S.emps || []).filter((e) => !qq || (e.employee_name + " " + e.employee_number + " " + e.name).toLowerCase().indexOf(qq) >= 0);
	q("#pe-list").innerHTML = `<table><tbody>${L.map((e) => `<tr class="click" data-act="pe-pick" data-e="${esc(e.name)}"><td><div class="emp-cell">${avatar(e.image, e.employee_name)}
		<div><b>${esc(e.employee_name)}</b><div class="muted">${esc([e.employee_number, e.designation, e.status !== "Active" ? e.status : ""].filter(Boolean).join(" · "))}</div></div></div></td></tr>`).join("")}</tbody></table>`;
}
function openLetter(fmt, emp) {
	window.open("/printview?doctype=Employee&name=" + encodeURIComponent(emp) + "&format=" + encodeURIComponent(fmt) + "&no_letterhead=0&trigger_print=0", "_blank");
}

// ------------------------------------------------------------------ BANK
const BANK_SHOW = [["check", "To check"], ["matched", "Matched to invoice"], ["noinv", "No invoice (remarked)"], ["all", "All entries"]];

async function bankAccounts() {
	const d = await call("bank_accounts", {});
	S.bankAccounts = d.accounts || [];
	S.bankReasons = d.reasons || [];
	return S.bankAccounts;
}
function accLabel(a) {
	return (a.account_name || a.name) + (a.bank_account_no ? " · " + String(a.bank_account_no).slice(-4).padStart(8, "•") : "");
}

async function viewBankAccounts(mode) {
	mode = mode || "overview";
	S.here = () => viewBankAccounts(mode);
	S.current = () => viewBankAccounts(mode);
	setMenu("bank");
	crumbs([["Bank", null], [mode === "upload" ? "Upload statement — pick the account" : mode === "check" ? "Daily check — pick the account" : "Bank accounts", null]],
		`<a data-act="go" data-go="new:Bank Account">+ Add bank account</a>`);
	loading();
	const list = await bankAccounts();
	const today = frappe.datetime.get_today();
	let h = `<h2 class="t">${mode === "upload" ? "Upload bank statement" : mode === "check" ? "Daily bank check" : "Bank accounts"}</h2>
		<div class="sub">Upload each account’s statement every day, then check every entry against a GST sales or purchase invoice.</div><div class="cards">`;
	list.forEach((a) => {
		const stale = !a.last_upload || String(a.last_upload) < today;
		h += `<div class="card" data-act="${mode === "upload" ? "bank-up" : "bank-chk"}" data-acc="${esc(a.name)}">
			<div class="n">${esc(a.account_name || a.name)}</div><div class="c">${esc(a.bank || "")}${a.bank_account_no ? " · A/c " + esc(a.bank_account_no) : ""}</div>
			<div class="f"><span>Statement up to</span><b>${a.last_date ? dt(a.last_date) : "—"}</b></div>
			<div class="f"><span>Last upload</span><b class="${stale ? "neg" : ""}">${a.last_upload ? dt(a.last_upload) : "never"}</b></div>
			<div class="f"><span>To check</span><b class="${a.to_check ? "neg" : ""}">${a.to_check || 0}</b></div>
			<div class="f"><span>Matched / no invoice</span><b>${a.matched || 0} / ${a.no_invoice || 0}</b></div>
			<div class="acts"><button class="btn sm pri" data-act="bank-up" data-acc="${esc(a.name)}">Upload statement</button>
				<button class="btn sm" data-act="bank-chk" data-acc="${esc(a.name)}">Check entries</button></div>
		</div>`;
	});
	h += `<div class="card" data-act="go" data-go="new:Bank Account"><div class="n">+ Add bank account</div>
		<div class="c">Bank, account number, IFSC and the ledger it posts to</div></div></div>`;
	if (!list.length) h += `<div class="hint">No company bank accounts yet. Add one first (tick “Is Company Account” and pick its bank ledger).</div>`;
	showView(h);
}

function bankGo(mode) {
	return bankAccounts().then((list) => {
		if (list.length === 1) return mode === "upload" ? viewBankUpload(list[0].name) : viewBankCheck(list[0].name);
		return viewBankAccounts(mode);
	});
}

// ---------- reading the statement file
function loadXlsx() {
	if (window.XLSX) return Promise.resolve(window.XLSX);
	const urls = ["https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js",
		"https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"];
	return urls.reduce((p, u) => p.catch(() => new Promise((res, rej) => {
		const s = document.createElement("script");
		s.src = u;
		s.onload = () => (window.XLSX ? res(window.XLSX) : rej(new Error("no XLSX")));
		s.onerror = () => rej(new Error("blocked"));
		document.head.appendChild(s);
	})), Promise.reject(new Error("start")));
}

function parseCsv(text) {
	const rows = [];
	let row = [], cell = "", qd = false;
	for (let i = 0; i < text.length; i++) {
		const ch = text[i];
		if (qd) {
			if (ch === '"' && text[i + 1] === '"') { cell += '"'; i++; }
			else if (ch === '"') qd = false;
			else cell += ch;
		} else if (ch === '"') qd = true;
		else if (ch === "," || ch === "\t" || ch === ";") { row.push(cell); cell = ""; }
		else if (ch === "\n" || ch === "\r") {
			if (ch === "\r" && text[i + 1] === "\n") i++;
			row.push(cell); rows.push(row); row = []; cell = "";
		} else cell += ch;
	}
	if (cell || row.length) { row.push(cell); rows.push(row); }
	return rows;
}

async function readStatement(file) {
	const name = file.name.toLowerCase();
	if (name.endsWith(".csv") || name.endsWith(".txt")) return parseCsv(await file.text());
	let X;
	try { X = await loadXlsx(); }
	catch (e) { throw new Error(__("Could not load the Excel reader. Save the statement as CSV and upload that instead.")); }
	const wb = X.read(await file.arrayBuffer(), { type: "array", cellDates: false });
	let best = [];
	wb.SheetNames.forEach((n) => {
		const rows = X.utils.sheet_to_json(wb.Sheets[n], { header: 1, raw: true, defval: "" });
		if (rows.length > best.length) best = rows;
	});
	return best;
}

const pad2 = (n) => String(n).padStart(2, "0");
const MONTHS = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };
function parseDate(v) {
	if (v === null || v === undefined || v === "") return "";
	if (typeof v === "number") {
		if (v < 20000 || v > 80000) return "";
		const d = new Date(Date.UTC(1899, 11, 30) + Math.round(v) * 86400000);
		return d.getUTCFullYear() + "-" + pad2(d.getUTCMonth() + 1) + "-" + pad2(d.getUTCDate());
	}
	const s = String(v).trim();
	let m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
	if (m) return m[1] + "-" + pad2(m[2]) + "-" + pad2(m[3]);
	let d, mo, y;
	m = s.match(/^(\d{1,2})[\/\-. ](\d{1,2})[\/\-. ](\d{2,4})/);
	if (m) { d = +m[1]; mo = +m[2]; y = +m[3]; }
	else {
		m = s.match(/^(\d{1,2})[\/\-. ]?([A-Za-z]{3})[A-Za-z]*[\/\-., ]*(\d{2,4})/);
		if (!m) return "";
		d = +m[1]; mo = MONTHS[m[2].toLowerCase()] || 0; y = +m[3];
	}
	if (y < 100) y += 2000;
	if (!mo || mo > 12 || !d || d > 31 || y < 2000 || y > 2100) return "";
	return y + "-" + pad2(mo) + "-" + pad2(d);
}
function parseAmt(v) {
	if (v === null || v === undefined || v === "") return { n: 0, side: "" };
	if (typeof v === "number") return { n: v, side: "" };
	const s = String(v).toLowerCase();
	const side = /\bdr\b|debit/.test(s) ? "dr" : /\bcr\b|credit/.test(s) ? "cr" : "";
	const n = parseFloat(s.replace(/[^0-9.\-]/g, "")) || 0;
	return { n: n, side: side };
}

function findHeader(rows) {
	for (let i = 0; i < Math.min(rows.length, 40); i++) {
		const j = rows[i].map((c) => String(c).toLowerCase()).join("|");
		if (/date/.test(j) && /(withdraw|debit|deposit|credit|amount|\bdr\b|\bcr\b)/.test(j)) return i;
	}
	return 0;
}
function guessMap(head) {
	const H = head.map((x) => String(x).toLowerCase().replace(/\s+/g, " ").trim());
	const find = (re, not) => H.findIndex((x) => re.test(x) && !(not && not.test(x)));
	const first = (...ix) => { for (const i of ix) if (i >= 0) return i; return -1; };
	const m = {
		date: first(find(/(txn|tran|transaction|posting).*date/), find(/^date$/), find(/date/, /value/), find(/date/)),
		description: find(/narration|description|particular|remark|details/),
		reference: find(/ref|chq|cheque|utr|instrument/),
		withdrawal: find(/withdraw|debit|^dr\.?$|dr amount|dr\.? amt/, /dr.?\/.?cr|cr.?\/.?dr/),
		deposit: find(/deposit|credit|^cr\.?$|cr amount|cr\.? amt/, /dr.?\/.?cr|cr.?\/.?dr/),
		amount: find(/^amount|txn amount|transaction amount|^amt/),
		drcr: find(/dr.?\/.?cr|cr.?\/.?dr|^type$|^dr\/cr$/),
		balance: find(/balance|^bal\.?$/),
	};
	if (m.reference === m.description) m.reference = -1;
	return m;
}

// reference number inside the narration (UPI id, NEFT/RTGS UTR, IMPS id) when the bank leaves the ref column empty
function refFromNarration(s) {
	const t = String(s || "");
	const m = t.match(/UPI\/(?:DR|CR)\/(\d{6,})/i) || t.match(/UTR[:\s\-]*([A-Z0-9]{8,})/i) || t.match(/IMPS[A-Z]*[\/\-\s:]*(?:[A-Z0-9]{1,4}[\/\-\s:]+)?(\d{9,})/i) || t.match(/IMPS[A-Z0-9]{0,4}?(\d{9,})/i)
		|| t.match(/(?:NEFT|RTGS)[\/\s\-:]*([A-Z]{4}[A-Z0-9]{8,})/i);
	return m ? m[1] : "";
}

function buildRows(raw, hi, m) {
	const out = [];
	for (let i = hi + 1; i < raw.length; i++) {
		const r = raw[i] || [];
		const date = m.date >= 0 ? parseDate(r[m.date]) : "";
		if (!date) continue;
		let wd = 0, dp = 0;
		if (m.withdrawal >= 0 || m.deposit >= 0) {
			wd = m.withdrawal >= 0 ? Math.abs(parseAmt(r[m.withdrawal]).n) : 0;
			dp = m.deposit >= 0 ? Math.abs(parseAmt(r[m.deposit]).n) : 0;
		} else if (m.amount >= 0) {
			const a = parseAmt(r[m.amount]);
			const t = m.drcr >= 0 ? String(r[m.drcr]).toLowerCase() : a.side;
			if (/dr|debit|withdraw/.test(t) || a.n < 0) wd = Math.abs(a.n); else dp = Math.abs(a.n);
		}
		if (!wd && !dp) continue;
		const desc = m.description >= 0 ? String(r[m.description]).replace(/\s+/g, " ").trim() : "";
		let ref = m.reference >= 0 ? String(r[m.reference]).trim() : "";
		if (!ref || ref === "-" || ref === "0") ref = refFromNarration(desc);
		const balTxt = m.balance >= 0 ? String(r[m.balance]).trim() : "";
		out.push({ date: date, description: desc, reference: ref, withdrawal: Math.round(wd * 100) / 100,
			deposit: Math.round(dp * 100) / 100, balance: balTxt, _bal: balTxt ? parseAmt(balTxt).n : null });
	}
	// Trust the running balance over the Debit/Credit columns (as for City Union Bank):
	// only for a statement in date order, and only where one side is filled in.
	const ordered = out.every((x, i) => !i || out[i - 1].date <= x.date);
	if (ordered && out.filter((x) => x._bal !== null).length > 1) {
		for (let i = 1; i < out.length; i++) {
			const a = out[i - 1], b = out[i];
			if (a._bal === null || b._bal === null || (b.withdrawal && b.deposit)) continue;
			const amt = b.withdrawal || b.deposit;
			const move = Math.round((b._bal - a._bal) * 100) / 100;
			if (Math.abs(Math.abs(move) - amt) > 0.01) continue;
			if (move < 0) { b.withdrawal = amt; b.deposit = 0; } else { b.deposit = amt; b.withdrawal = 0; }
		}
	}
	out.forEach((x) => delete x._bal);
	return out;
}

// A sample statement laid out like City Union Bank's net-banking Excel download
function sampleStatement(a) {
	const t = new Date();
	const d = (k) => { const x = new Date(t.getFullYear(), t.getMonth(), t.getDate() - k); return pad2(x.getDate()) + "/" + pad2(x.getMonth() + 1) + "/" + x.getFullYear(); };
	const lines = [
		[d(3), "NEFT CR-SBIN0001234-ASHOK LEYLAND LTD-UTR:SBIN226313456789", "", "", "3469200.00"],
		[d(3), "UPI/DR/431298765412/SRI BALAJI CEMENT/HDFC/Payment", "", "38500.00", ""],
		[d(2), "CHQ PAID-RK TRANSPORTS", "001234", "17640.00", ""],
		[d(2), "IMPS/P2A/431511223344/RAMESH KUMAR/SITE WAGES", "", "25000.00", ""],
		[d(1), "RTGS CR-HDFC0000060-TVS LOGISTICS PVT LTD-UTR:HDFCR52026111100123", "", "", "490000.00"],
		[d(1), "SMS CHARGES QTR", "", "118.00", ""],
		[d(0), "CASH WITHDRAWAL - SITE PETTY CASH", "", "50000.00", ""],
	];
	let bal = 1250000;
	const rows = lines.map((l) => { bal = bal - (+l[3] || 0) + (+l[4] || 0); return l.concat([bal.toFixed(2)]); });
	const dr = lines.reduce((s, l) => s + (+l[3] || 0), 0), cr = lines.reduce((s, l) => s + (+l[4] || 0), 0);
	return [["CITY UNION BANK LTD"], ["STATEMENT OF ACCOUNT"], [], ["Account Number", String((a && a.bank_account_no) || "510909010012345")],
		["Account Name", String(S.company || "SHIV BHARAT INFRASTRUCTURES")], ["Branch", "CHENNAI"], ["Period", d(3) + " to " + d(0)],
		["Opening Balance", "1250000.00"], [], ["DATE", "DESCRIPTION", "CHEQUE NO", "DEBIT", "CREDIT", "BALANCE"]]
		.concat(rows).concat([["TOTAL", "", "", dr.toFixed(2), cr.toFixed(2), ""]]);
}

async function downloadSample(accName) {
	const a = (S.bankAccounts || []).find((x) => x.name === accName) || {};
	const aoa = sampleStatement(a);
	try {
		const X = await loadXlsx();
		const wb = X.utils.book_new();
		const ws = X.utils.aoa_to_sheet(aoa);
		ws["!cols"] = [{ wch: 12 }, { wch: 62 }, { wch: 12 }, { wch: 14 }, { wch: 14 }, { wch: 16 }];
		X.utils.book_append_sheet(wb, ws, "Statement");
		X.writeFile(wb, "Bank_statement_sample.xlsx");
	} catch (e) {
		const csv = aoa.map((r) => r.map((c) => /[",]/.test(String(c)) ? '"' + String(c).replace(/"/g, '""') + '"' : c).join(",")).join("\n");
		const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
		const link = document.createElement("a");
		link.href = url; link.download = "Bank_statement_sample.csv"; document.body.appendChild(link); link.click(); link.remove();
		setTimeout(() => URL.revokeObjectURL(url), 2000);
	}
}

async function viewBankUpload(accName) {
	S.here = () => viewBankUpload(accName);
	setMenu("bank");
	if (!S.bankAccounts) await bankAccounts();
	const a = (S.bankAccounts || []).find((x) => x.name === accName) || { name: accName };
	crumbs([["Bank", () => viewBankAccounts("overview")], [a.account_name || accName, () => viewBankCheck(accName)], ["Upload statement", null]]);
	S.bu = { acc: accName, raw: null };
	showView(`<h2 class="t">Upload statement — ${esc(a.account_name || accName)}</h2>
		<div class="sub">Download today’s statement from the bank (Excel .xls / .xlsx, or CSV) and choose it here. Entries already uploaded are skipped, so overlapping dates are fine.
		${a.last_date ? " Last statement entry: <b>" + dt(a.last_date) + "</b>." : ""}</div>
		<div class="upgrid">
			<label class="drop" for="bu-file">${ICON("upload")}<b>Choose the statement file</b><span>Excel (.xls, .xlsx) or CSV — or drop it here</span>
				<input type="file" id="bu-file" accept=".xls,.xlsx,.csv,.txt"></label>
			<div class="box howto"><h3>${ICON("info")} Getting the Excel from the bank</h3>
				<ol><li><b>City Union Bank:</b> Net Banking → Accounts → Account Statement → pick the account and dates → Format <b>Excel</b> → Download.</li>
				<li>Other banks: download the statement as Excel or CSV, not PDF.</li>
				<li>Upload it as it is — the bank’s title lines and the TOTAL line are skipped by themselves.</li></ol>
				<button class="btn" data-act="bu-sample" data-acc="${esc(accName)}">${ICON("download")} Download sample Excel</button></div>
		</div>
		<div id="bu-out"></div>`);
}

function buRender() {
	const b = S.bu;
	const head = (b.raw[b.hi] || []).map((h, i) => String(h || "Column " + (i + 1)));
	const fields = [["date", "Date *"], ["description", "Narration"], ["reference", "Cheque / ref no"], ["withdrawal", "Withdrawal (debit)"],
		["deposit", "Deposit (credit)"], ["amount", "Single amount column"], ["drcr", "Dr / Cr column"], ["balance", "Balance"]];
	const sel = (f) => `<select class="bu-map" data-f="${f}"><option value="-1">— none —</option>${head.map((h, i) =>
		`<option value="${i}" ${b.map[f] === i ? "selected" : ""}>${esc(h).slice(0, 40)}</option>`).join("")}</select>`;
	b.rows = buildRows(b.raw, b.hi, b.map);
	const dep = b.rows.reduce((s, r) => s + r.deposit, 0), wd = b.rows.reduce((s, r) => s + r.withdrawal, 0);
	const dates = b.rows.map((r) => r.date).sort();
	let h = `<div class="box"><h3>Columns <span class="muted">found automatically — change any that are wrong</span></h3>
		<div class="bar"><label class="muted">Heading row <input type="number" id="bu-hi" min="1" value="${b.hi + 1}" style="width:70px"></label></div>
		<div class="mapgrid">${fields.map((f) => `<label><span>${f[1]}</span>${sel(f[0])}</label>`).join("")}</div></div>`;
	h += `<div class="tiles"><div class="tile"><div class="l">Entries</div><div class="v">${b.rows.length}</div><div class="s">${dates.length ? dt(dates[0]) + " – " + dt(dates[dates.length - 1]) : ""}</div></div>
		<div class="tile"><div class="l">Money in (deposits)</div><div class="v">${money(dep)}</div></div>
		<div class="tile"><div class="l">Money out (withdrawals)</div><div class="v">${money(wd)}</div></div></div>`;
	if (b.rows.length) {
		h += `<div class="bar"><button class="btn pri" data-act="bu-save">Save ${b.rows.length} entries to ${esc(b.accLabel)}</button></div>
			<div class="box"><table><thead><tr><th>Date</th><th>Narration</th><th>Ref</th><th class="r">Withdrawal</th><th class="r">Deposit</th><th class="r">Balance</th></tr></thead><tbody>`;
		b.rows.slice(0, 25).forEach((r) => {
			h += `<tr><td>${dt(r.date)}</td><td>${esc(r.description).slice(0, 90)}</td><td>${esc(r.reference)}</td>
				<td class="r">${r.withdrawal ? money(r.withdrawal) : ""}</td><td class="r">${r.deposit ? money(r.deposit) : ""}</td><td class="r muted">${esc(r.balance)}</td></tr>`;
		});
		h += `</tbody></table>${b.rows.length > 25 ? `<div class="hint">… and ${b.rows.length - 25} more</div>` : ""}</div>`;
	} else {
		h += `<div class="warn">No entries read. Check the Date column and the Withdrawal / Deposit (or Amount) columns above, and the heading row number.</div>`;
	}
	q("#bu-out").innerHTML = h;
}

async function buFile(file) {
	q("#bu-out").innerHTML = `<div class="hint">Reading ${esc(file.name)}…</div>`;
	try {
		const raw = (await readStatement(file)).filter((r) => r && r.some((c) => String(c).trim() !== ""));
		const hi = findHeader(raw);
		const a = (S.bankAccounts || []).find((x) => x.name === S.bu.acc) || {};
		Object.assign(S.bu, { raw: raw, hi: hi, map: guessMap(raw[hi] || []), accLabel: a.account_name || S.bu.acc });
		buRender();
	} catch (e) {
		q("#bu-out").innerHTML = `<div class="warn">${esc(e.message || e)}</div>`;
	}
}

async function buSave(el) {
	const b = S.bu;
	el.disabled = true;
	frappe.dom.freeze(__("Saving {0} bank entries…", [b.rows.length]));
	try {
		const r = await call("bank_upload", { bank_account: b.acc, rows: JSON.stringify(b.rows) });
		frappe.dom.unfreeze();
		frappe.show_alert({ message: __("{0} new entries saved, {1} already there", [r.made, r.skipped]), indicator: "green" }, 6);
		S.bankAccounts = null;
		viewBankCheck(b.acc);
	} catch (e) {
		frappe.dom.unfreeze();
		el.disabled = false;
	}
}

// ---------- the daily check
async function viewBankCheck(accName, show) {
	show = show || (S.bankShow || "check");
	S.bankShow = show;
	S.bankAcc = accName;
	S.here = () => viewBankCheck(accName, show);
	S.current = () => viewBankCheck(accName, show);
	setMenu("bank");
	if (!S.bankAccounts) await bankAccounts();
	const a = (S.bankAccounts || []).find((x) => x.name === accName) || { name: accName };
	crumbs([["Bank", () => viewBankAccounts("overview")], [a.account_name || accName, null]],
		`<a data-act="bank-up" data-acc="${esc(accName)}">↑ Upload statement</a>`);
	const keepScroll = q("#view").scrollTop;
	if (!S.bankKeep) loading();
	const r = periodRange(S.period);
	const d = await call("bank_list", { bank_account: accName, show: show, from_date: r[0], to_date: r[1] });
	const c = d.counts || {};
	const reasons = d.reasons || S.bankReasons || [];
	let h = `<h2 class="t">Bank check — ${esc(a.account_name || accName)}</h2>
		<div class="sub">For each entry pick the GST invoice it belongs to. If there is no invoice, choose why and write a remark.</div>
		${periodBar(`<select id="bk-acc">${(S.bankAccounts || []).map((x) => `<option value="${esc(x.name)}" ${x.name === accName ? "selected" : ""}>${esc(accLabel(x))}</option>`).join("")}</select>
		<select id="bk-show">${BANK_SHOW.map((s) => `<option value="${s[0]}" ${s[0] === show ? "selected" : ""}>${s[1]}</option>`).join("")}</select>`)}
		<div class="tiles"><div class="tile go" data-act="bk-show" data-show="check"><div class="l">To check</div><div class="v ${c.to_check ? "neg" : ""}">${c.to_check || 0}</div></div>
			<div class="tile go" data-act="bk-show" data-show="matched"><div class="l">Matched to invoice</div><div class="v">${c.matched || 0}</div></div>
			<div class="tile go" data-act="bk-show" data-show="noinv"><div class="l">No invoice, remarked</div><div class="v">${c.no_invoice || 0}</div></div>
			<div class="tile go" data-act="bk-show" data-show="all"><div class="l">All entries in period</div><div class="v">${c.total || 0}</div></div></div>`;
	const rows = d.rows || [];
	if (!rows.length) {
		h += `<div class="hint">${show === "check" ? "Nothing left to check in this period. ✔" : "No entries here."}
			${!c.total ? ` <a data-act="bank-up" data-acc="${esc(accName)}">Upload a statement</a>` : ""}</div>`;
	}
	rows.forEach((t) => {
		const inn = Number(t.deposit || 0) > 0;
		const amt = inn ? t.deposit : t.withdrawal;
		h += `<div class="bt ${t.st === "Matched" ? "ok" : t.st ? "nb" : ""}">
			<div class="bt-h"><div class="bt-d">${dt(t.date)}</div>
				<div class="bt-n">${esc(t.description || "(no narration)")}${t.ref ? `<span class="muted"> · ref ${esc(t.ref)}</span>` : ""}</div>
				<div class="bt-m ${inn ? "in" : "outm"}">${inn ? "+ " : "− "}${money(amt)}<span>${inn ? "money in → sales invoice" : "money out → purchase invoice"}</span></div></div>
			<div class="bt-a">`;
		if (t.st === "Matched") {
			const mi = (t.minfo || [])[0] || {};
			h += `<span class="pill green">✔ Matched</span> <a data-act="open" data-dt="${esc(t.mdt)}" data-name="${esc(t.mname)}">${esc(t.mname)}</a>
				<span class="muted">${esc(mi.party || "")}${mi.g ? " · " + money(mi.g) : ""}${mi.project ? " · " + esc(pLabel(findProject(mi.project))) : ""}</span>
				${t.remarks ? `<span class="muted"> · ${esc(t.remarks)}</span>` : ""}
				<button class="btn sm" data-act="bk-undo" data-txn="${esc(t.name)}">Undo</button>`;
		} else if (t.st === "No Invoice") {
			h += `<span class="pill orange">No invoice</span> <b>${esc(t.reason || "")}</b> — ${esc(t.remarks || "")}
				<span class="muted">${t.checked_by ? " · " + esc(t.checked_by) : ""}</span>
				<button class="btn sm" data-act="bk-undo" data-txn="${esc(t.name)}">Undo</button>`;
		} else {
			if ((t.cands || []).length) {
				h += `<div class="bt-c"><span class="muted">Possible invoice:</span>${t.cands.map((x) => `
					<button class="cand" data-act="bk-match" data-txn="${esc(t.name)}" data-dt="${esc(x.doctype)}" data-name="${esc(x.name)}"
						title="${esc(x.note)}"><b>${esc(x.name)}</b> ${esc(x.party || "")} · ${money(x.amount)} · ${dt(x.date)}
						<span class="${x.note.indexOf("exact") === 0 ? "ex" : "nx"}">${esc(x.note)}</span></button>`).join("")}</div>`;
			} else {
				h += `<div class="bt-c"><span class="warn">No ${inn ? "sales" : "purchase"} invoice with this amount.</span></div>`;
			}
			h += `<div class="bt-f">
				<input class="bk-inv" data-txn="${esc(t.name)}" placeholder="Other invoice no.">
				<button class="btn sm" data-act="bk-other" data-txn="${esc(t.name)}">Match</button>
				<span class="sep2">or</span>
				<select class="bk-rsn" data-txn="${esc(t.name)}"><option value="">No invoice — why?</option>${reasons.map((x) => `<option>${esc(x)}</option>`).join("")}</select>
				<input class="bk-rem" data-txn="${esc(t.name)}" placeholder="Remark (what is this entry?)">
				<button class="btn sm pri" data-act="bk-noinv" data-txn="${esc(t.name)}">Save remark</button></div>`;
		}
		h += `</div></div>`;
	});
	showView(h);
	if (S.bankKeep) { q("#view").scrollTop = keepScroll; S.bankKeep = false; }
}

async function bankSet(args) {
	await call("bank_set", args);
	S.bankKeep = true;
	S.bankAccounts = null;
	viewBankCheck(S.bankAcc, S.bankShow);
}

async function viewBankNoInv() {
	S.here = viewBankNoInv;
	S.current = viewBankNoInv;
	setMenu("bank");
	crumbs([["Bank", () => viewBankAccounts("overview")], ["Entries without invoice", null]]);
	loading();
	const r = periodRange(S.period);
	const d = await call("bank_noinv", { from_date: r[0], to_date: r[1] });
	const rows = d.rows || [];
	const tin = rows.reduce((s, x) => s + Number(x.deposit || 0), 0), tout = rows.reduce((s, x) => s + Number(x.withdrawal || 0), 0);
	let h = `<h2 class="t">Bank entries without a GST invoice</h2><div class="sub">Every entry marked “no invoice”, with the reason and remark given.</div>
		${periodBar()}
		<div class="tiles"><div class="tile"><div class="l">Entries</div><div class="v">${rows.length}</div></div>
			<div class="tile"><div class="l">Money in without invoice</div><div class="v">${money(tin)}</div></div>
			<div class="tile"><div class="l">Money out without invoice</div><div class="v">${money(tout)}</div></div></div>
		<div class="box"><table><thead><tr><th>Date</th><th>Bank</th><th>Narration</th><th class="r">In</th><th class="r">Out</th><th>Reason</th><th>Remark</th><th>By</th></tr></thead><tbody>`;
	rows.forEach((x) => {
		h += `<tr class="click" data-act="open" data-dt="Bank Transaction" data-name="${esc(x.name)}"><td>${dt(x.date)}</td><td>${esc(x.bank_account)}</td>
			<td>${esc((x.description || "").slice(0, 70))}</td><td class="r">${x.deposit ? money(x.deposit) : ""}</td><td class="r">${x.withdrawal ? money(x.withdrawal) : ""}</td>
			<td>${esc(x.reason)}</td><td>${esc(x.remarks)}</td><td class="muted">${esc(x.checked_by)}</td></tr>`;
	});
	if (!rows.length) h += `<tr><td colspan="8" class="hint">None in this period.</td></tr>`;
	h += `</tbody></table></div>`;
	showView(h);
}

// ------------------------------------------------------------------ PROJECT BOQ (type or upload, per stage)
const BOQ_TYPES = ["Material", "Manpower", "Equipment", "Transport", "Subcontract", "Other"];
const BOQ_TONE = { Material: "blue", Manpower: "green", Equipment: "amber", Transport: "teal", Subcontract: "violet", Other: "red" };

function boqBack(p) {
	return [["Project BOQ", () => go("boq", "projects")], [pLabel(p), () => viewBoqStages(p)]];
}

async function viewBoqStages(p) {
	S.here = () => viewBoqStages(p);
	setMenu("projects");
	crumbs([["Project BOQ", () => go("boq", "projects")], [pLabel(p), null]]);
	loading();
	const d = await call("boq_stages", { project: p.name });
	const stages = d.stages || [];
	const master = (d.master || []).filter((m) => !stages.some((s) => s.stage === m));
	let h = `<h2 class="t">Project BOQ — ${esc(pLabel(p))}</h2>
		<div class="sub">Pick the milestone / stage, then type the BOQ lines or upload them from Excel.${d.boq ? " BOQ record: " + esc(d.boq) + "." : ""}</div>`;
	if (!stages.length) h += `<div class="warn">This project has no stages yet. Create the first stage below.</div>`;
	h += `<div class="cards">`;
	stages.forEach((s) => {
		h += `<div class="card" data-act="boq-edit" data-p="${esc(p.name)}" data-stage="${esc(s.stage)}">
			<div class="n">${esc(s.stage)}</div><div class="c">${esc(s.source)}</div>
			<div class="f"><span>BOQ lines</span><b>${s.lines}</b></div>
			<div class="f"><span>BOQ value</span><b>${money(s.amount)}</b></div>
			<div class="f"><span></span>${s.lines ? `<span class="pill green">has BOQ</span>` : `<span class="pill orange">no BOQ yet</span>`}</div></div>`;
	});
	h += `<div class="card newstage"><div class="n">${ICON("plus")} New stage</div>
		<div class="c">Pick a standard stage or type a new name</div>
		<select id="ns-pick"><option value="">— standard stages —</option>${master.map((m) => `<option>${esc(m)}</option>`).join("")}</select>
		<input id="ns-name" placeholder="or type a new stage name">
		<button class="btn pri sm" data-act="boq-newstage" data-p="${esc(p.name)}">Create and open</button></div>`;
	h += `</div>`;
	showView(h);
}

async function boqNewStage(el) {
	const p = findProject(el.dataset.p);
	const typed = ((q("#ns-name") || {}).value || "").trim();
	const picked = (q("#ns-pick") || {}).value || "";
	if (!typed && !picked) { frappe.msgprint(__("Pick a standard stage or type a new stage name.")); return; }
	let stage = picked;
	if (typed) {
		const r = await call("boq_add_stage", { stage_name: typed });
		stage = r.stage;
	}
	viewBoqEdit(p, stage);
}

async function viewBoqEdit(p, stage) {
	S.here = () => viewBoqEdit(p, stage);
	setMenu("projects");
	crumbs(boqBack(p).concat([[stage, null]]));
	loading();
	const d = await call("boq_get", { project: p.name, stage: stage });
	S.boqEd = { p: p, stage: stage, boq: d.boq, rows: (d.rows || []).map((r) => Object.assign({}, r)), dirty: false };
	if (!S.boqEd.rows.length) S.boqEd.rows = [boqBlank(1), boqBlank(2), boqBlank(3)];
	boqRender();
}

function boqBlank(n) {
	return { sl: String(n), description: "", type: "Material", unit: "", qty: "", rate: "", remarks: "" };
}

function boqRender() {
	const b = S.boqEd;
	let h = `<h2 class="t">BOQ — ${esc(pLabel(b.p))} · ${esc(b.stage)}</h2>
		<div class="sub">One line per item. Type tells where the cost belongs (material, manpower, equipment, transport, subcontract, other). Rate is optional — with it, the budget by type is worked out.</div>
		<div class="bar">
			<label class="btn">${ICON("upload")} Upload Excel<input type="file" id="boq-file" accept=".xls,.xlsx,.csv,.txt" hidden></label>
			<button class="btn" data-act="boq-sample">${ICON("download")} Download sample Excel</button>
			<button class="btn" data-act="boq-add">${ICON("plus")} Add line</button>
			<button class="btn pri" data-act="boq-save">${ICON("check")} Save BOQ</button>
			<span class="muted" id="boq-state">${b.dirty ? "unsaved changes" : ""}</span>
		</div>
		<div class="tiles boqt" id="boq-tot"></div>
		<div class="box boqbox"><table class="boqg"><thead><tr><th style="width:62px">Sl. No.</th><th>Item description</th><th style="width:130px">Type</th>
			<th style="width:84px">Unit</th><th class="r" style="width:100px">Quantity</th><th class="r" style="width:110px">Rate</th><th class="r" style="width:120px">Amount</th>
			<th style="width:200px">Remarks</th><th style="width:34px"></th></tr></thead><tbody>`;
	b.rows.forEach((r, i) => {
		h += `<tr><td><input class="bg" data-i="${i}" data-f="sl" value="${esc(r.sl)}"></td>
			<td><input class="bg wide" data-i="${i}" data-f="description" value="${esc(r.description)}" placeholder="e.g. RCC M25 footings"></td>
			<td><select class="bg ty-${BOQ_TONE[r.type] || "red"}" data-i="${i}" data-f="type">${BOQ_TYPES.map((t) => `<option ${t === r.type ? "selected" : ""}>${t}</option>`).join("")}</select></td>
			<td><input class="bg" data-i="${i}" data-f="unit" value="${esc(r.unit)}" placeholder="Cu.m"></td>
			<td><input class="bg r" type="number" step="any" data-i="${i}" data-f="qty" value="${r.qty === "" ? "" : esc(r.qty)}"></td>
			<td><input class="bg r" type="number" step="any" data-i="${i}" data-f="rate" value="${r.rate === "" || r.rate === 0 ? "" : esc(r.rate)}" placeholder="optional"></td>
			<td class="r amt" id="boq-amt-${i}">${Number(r.qty || 0) * Number(r.rate || 0) ? money(Number(r.qty || 0) * Number(r.rate || 0)) : "—"}</td>
			<td><input class="bg" data-i="${i}" data-f="remarks" value="${esc(r.remarks)}"></td>
			<td><button class="xbtn" data-act="boq-del" data-i="${i}" title="Remove line">×</button></td></tr>`;
	});
	h += `</tbody></table><div class="bar" style="margin:10px 0 0"><button class="btn sm" data-act="boq-add">${ICON("plus")} Add line</button>
		<span class="muted">${b.rows.filter((r) => (r.description || "").trim()).length} line(s)</span></div></div>`;
	const keep = q("#view").scrollTop;
	showView(h);
	q("#view").scrollTop = keep;
	boqTotals();
}

function boqTotals() {
	const b = S.boqEd;
	const t = {};
	BOQ_TYPES.forEach((x) => (t[x] = 0));
	let all = 0;
	b.rows.forEach((r) => { const a = Number(r.qty || 0) * Number(r.rate || 0); t[r.type] = (t[r.type] || 0) + a; all += a; });
	const el = q("#boq-tot");
	if (el) el.innerHTML = BOQ_TYPES.map((x) => `<div class="tile ti-${BOQ_TONE[x]}"><div class="tbody"><div class="l">${x}</div><div class="v">${money(t[x])}</div></div></div>`).join("") +
		`<div class="tile"><div class="tbody"><div class="l">Total BOQ (this stage)</div><div class="v">${money(all)}</div></div></div>`;
}

function boqInput(el) {
	const b = S.boqEd;
	const i = Number(el.dataset.i), f = el.dataset.f;
	b.rows[i][f] = el.value;
	b.dirty = true;
	const st = q("#boq-state");
	if (st) st.textContent = "unsaved changes";
	if (f === "qty" || f === "rate") {
		const a = Number(b.rows[i].qty || 0) * Number(b.rows[i].rate || 0);
		const c = q("#boq-amt-" + i);
		if (c) c.textContent = a ? money(a) : "—";
	}
	if (f === "type") el.className = "bg ty-" + (BOQ_TONE[el.value] || "red");
	boqTotals();
}

// ---------- BOQ Excel
function boqType(v) {
	const s = String(v || "").toLowerCase();
	if (!s) return "Material";
	if (/man ?power|labou?r|worker|mason|helper/.test(s)) return "Manpower";
	if (/equip|machine|crane|jcb|hire|rent/.test(s)) return "Equipment";
	if (/transport|freight|lorry|truck|shifting|carting/.test(s)) return "Transport";
	if (/sub.?contract|contractor|job ?work/.test(s)) return "Subcontract";
	if (/material|mat\b|supply|steel|cement/.test(s)) return "Material";
	return "Other";
}

function boqFromSheet(raw) {
	let hi = 0;
	for (let i = 0; i < Math.min(raw.length, 30); i++) {
		const j = raw[i].map((c) => String(c).toLowerCase()).join("|");
		if (/desc|item|particular|work/.test(j) && /qty|quantity/.test(j)) { hi = i; break; }
	}
	const H = (raw[hi] || []).map((x) => String(x).toLowerCase().replace(/\s+/g, " ").trim());
	const f = (re, not) => H.findIndex((x) => re.test(x) && !(not && not.test(x)));
	const m = { sl: f(/^s\.? ?l|^sl|^s\.? ?no|^sr|^#$|^no\.?$/), description: f(/desc|item|particular|work/, /^s\.? ?l|^sl|no\.?$/), type: f(/type|category|head|nature/),
		unit: f(/^unit|uom/), qty: f(/qty|quantity/), rate: f(/rate|price/), remarks: f(/remark|note|comment/) };
	if (m.description < 0) throw new Error(__("Could not find the Item description column. Use the sample Excel layout."));
	const rows = [];
	for (let i = hi + 1; i < raw.length; i++) {
		const r = raw[i] || [];
		const desc = String(r[m.description] || "").replace(/\s+/g, " ").trim();
		if (!desc || /^total/i.test(desc)) continue;
		const num = (k) => (m[k] >= 0 ? parseAmt(r[m[k]]).n : 0) || "";
		rows.push({ sl: m.sl >= 0 && String(r[m.sl]).trim() ? String(r[m.sl]).trim() : String(rows.length + 1), description: desc,
			type: m.type >= 0 ? boqType(r[m.type]) : boqType(desc), unit: m.unit >= 0 ? String(r[m.unit] || "").trim() : "",
			qty: num("qty"), rate: num("rate"), remarks: m.remarks >= 0 ? String(r[m.remarks] || "").trim() : "" });
	}
	return rows;
}

async function boqFile(file) {
	try {
		const raw = (await readStatement(file)).filter((r) => r && r.some((c) => String(c).trim() !== ""));
		const rows = boqFromSheet(raw);
		if (!rows.length) { frappe.msgprint(__("No BOQ lines found in this file.")); return; }
		const b = S.boqEd;
		const has = b.rows.some((r) => (r.description || "").trim());
		const apply = (replace) => {
			b.rows = replace ? rows : b.rows.filter((r) => (r.description || "").trim()).concat(rows);
			b.dirty = true;
			boqRender();
			frappe.show_alert({ message: __("{0} line(s) read from {1}. Check them, then Save BOQ.", [rows.length, file.name]), indicator: "blue" }, 6);
		};
		if (!has) apply(true);
		else frappe.confirm(__("Replace the {0} line(s) on screen with the {1} from the file? (No = add them below)", [b.rows.length, rows.length]), () => apply(true), () => apply(false));
	} catch (e) {
		frappe.msgprint(esc(e.message || e));
	}
}

function boqSampleAoa() {
	return [["Sl. No.", "Item description", "Type", "Unit", "Quantity", "Rate (optional)", "Remarks"],
		[1, "Excavation in ordinary soil for footings", "Manpower", "Cu.m", 420, 350, ""],
		[2, "PCC 1:4:8 below footings", "Material", "Cu.m", 38, 5200, ""],
		[3, "RCC M25 for footings and pedestals", "Material", "Cu.m", 96, 7800, "Ready-mix"],
		[4, "TMT reinforcement steel Fe500D", "Material", "MT", 9.6, 68000, ""],
		[5, "Bar bending and fixing labour", "Manpower", "MT", 9.6, 6500, ""],
		[6, "JCB hire for excavation", "Equipment", "Hrs", 60, 1200, "With operator and diesel"],
		[7, "Hydra crane for steel erection", "Equipment", "Days", 12, 9000, ""],
		[8, "Steel structure erection", "Subcontract", "MT", 85, 4500, "Erection contractor"],
		[9, "Material shifting from yard to site", "Transport", "Trips", 25, 3500, ""],
		[10, "Site safety and housekeeping", "Other", "LS", 1, 25000, ""]];
}

async function boqSample() {
	const aoa = boqSampleAoa();
	const types = [["Type", "Use for"], ["Material", "Cement, steel, sheets, bolts, paint, any supply"], ["Manpower", "Labour, masons, helpers, bar benders"],
		["Equipment", "JCB, crane, mixer, scaffolding - hire or own"], ["Transport", "Lorry, trips, material shifting, freight"],
		["Subcontract", "Work given to a contractor (erection, roofing, painting)"], ["Other", "Anything else"]];
	try {
		const X = await loadXlsx();
		const wb = X.utils.book_new();
		const ws = X.utils.aoa_to_sheet(aoa);
		ws["!cols"] = [{ wch: 8 }, { wch: 46 }, { wch: 14 }, { wch: 8 }, { wch: 11 }, { wch: 15 }, { wch: 30 }];
		X.utils.book_append_sheet(wb, ws, "BOQ");
		const wt = X.utils.aoa_to_sheet(types);
		wt["!cols"] = [{ wch: 14 }, { wch: 60 }];
		X.utils.book_append_sheet(wb, wt, "Types");
		X.writeFile(wb, "BOQ_sample.xlsx");
	} catch (e) {
		const csv = aoa.map((r) => r.map((c) => /[",]/.test(String(c)) ? '"' + String(c).replace(/"/g, '""') + '"' : c).join(",")).join("\n");
		const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
		const a = document.createElement("a");
		a.href = url; a.download = "BOQ_sample.csv"; document.body.appendChild(a); a.click(); a.remove();
		setTimeout(() => URL.revokeObjectURL(url), 2000);
	}
}

async function boqSave(el) {
	const b = S.boqEd;
	const rows = b.rows.filter((r) => (r.description || "").trim());
	const noQty = rows.filter((r) => !(Number(r.qty) > 0)).length;
	const go2 = async () => {
		el.disabled = true;
		try {
			const r = await call("boq_save", { project: b.p.name, stage: b.stage, rows: JSON.stringify(rows) });
			frappe.show_alert({ message: __("BOQ saved: {0} line(s) for {1}", [r.lines, b.stage]), indicator: "green" }, 5);
			viewBoqEdit(b.p, b.stage);
		} catch (e) { el.disabled = false; }
	};
	if (!rows.length) {
		frappe.confirm(__("No lines with a description. Save an empty BOQ for this stage (removes its lines)?"), go2);
	} else if (noQty) {
		frappe.confirm(__("{0} line(s) have no quantity. Save anyway?", [noQty]), go2);
	} else go2();
}

// ------------------------------------------------------------------ HELP (written for someone new to computers and ERP)
const HELP = {
	home: { title: "Home", where: "Click “Lite ERP” at the top left", color: "#c8102e",
		intro: "Home is like the front page of a newspaper. It tells you, in one look, how the company is doing today.",
		steps: [["Look at the boxes", "Each box shows one number. For example “To receive from customers” is the money customers still have to pay you."],
			["Red means “please look”", "If a number is red, something needs your attention. Example: money that is late, or today’s bank statement not uploaded."],
			["Click a box to see more", "Clicking a box opens the full list behind that number. To come back, click “Lite ERP” at the top left."],
			["See the chart", "Red bars are sales (money you billed). Grey bars are purchases (money you spent). Taller red bars are good news."],
			["Bill what is due", "“Milestones to bill” shows work that is finished and ready for billing. Click one to make its bill."]],
		example: "Today the box “To receive from customers” shows ₹ 69 lakh and “overdue ₹ 23 lakh” in red. That means customers owe you ₹ 69 lakh, and ₹ 23 lakh of it should already have been paid. You can call those customers.",
		words: [["Overdue", "Late. The last date to pay has passed."], ["Balance", "What is left after adding and subtracting."]],
		links: [["home", "Open Home"]] },
	projects: { title: "Projects & BOQ", where: "Projects menu", color: "#2563eb",
		intro: "A project is one building work (one site). A BOQ is the shopping list for that work: what is needed, how much, and roughly what it costs.",
		steps: [["Open Project BOQ", "Click Projects at the top, then “Project BOQ”."],
			["Choose the project", "You will see all projects as cards. Type a few letters in the search box to find one quickly, then click it."],
			["Choose the stage", "Work happens in stages, like Foundation, Steel Structure, Roofing. Click the stage. If there is no stage, type a name in “New stage” and click “Create and open”."],
			["Write the list", "Fill one line for each item: what it is, its type, unit (bags, kg, trips), and how many. Rate (price for one) is optional."],
			["Or upload from Excel", "If the list is already in Excel, click “Upload Excel”. Not sure how the Excel should look? Click “Download sample Excel” and copy that layout."],
			["Save", "Click the red “Save BOQ” button. If you forget and try to leave, the screen will remind you."]],
		example: "For the Foundation stage you write: “Cement – Material – Bags – 500”, “JCB – Equipment – Hours – 60”, “Masons – Manpower – Days – 30”. Later, when you buy cement, the app knows cement belongs to this stage.",
		words: [["Project", "One building job at one site."], ["Stage / milestone", "One part of the job, like Foundation or Roofing."],
			["BOQ", "Bill of Quantities – the list of items and quantities needed for the work."],
			["Type", "What kind of cost: Material (things you buy), Manpower (workers), Equipment (machines), Transport (lorries), Subcontract (work given to another contractor), Other."]],
		links: [["boq", "Open Project BOQ"], ["projects", "See all projects"]] },
	sales: { title: "Sales (orders and bills to the customer)", where: "Sales menu", color: "#16a34a",
		intro: "First you write the customer’s order (sales order). Then you bill it. Lines marked MS = Yes are billed in parts, one bill for each finished milestone. Lines marked MS = No are billed separately whenever they are done.",
		steps: [["Make the sales order", "Click Sales → “New sales order” (or open a project and click “New sales order”). Choose the customer, the item code and GST."],
			["Write the lines", "One line for each item: Sl. No., Description, Area (or quantity), Unit (sq.ft, sq.m, Nos …) and Cost per unit. The total is worked out for you. Click “Bring lines from the project BOQ” to fill them quickly."],
			["Say MS Yes or No", "MS means milestone. Yes = this line is billed part by part with the milestones. No = this line is billed on its own (for example an extra gate)."],
			["Make the milestones", "In step 3, click “Project stages” or a quick start like 30/40/30. The % is of the MS work only. They must add up to 100%."],
			["Create and Submit", "Click “Create sales order”. The order opens below – check it and click Submit once."],
			["Bill a milestone", "Sales → “Bill a milestone” → the project. Blue card = ready to bill, yellow = draft bill, green = billed. Click a blue card: the bill opens with every MS line at that %."],
			["Non-MS bill", "Sales → “Non-MS bill” → the project. You see the MS = No lines and what is left to bill. Click “Make non-MS invoice”. You can lower the quantity if only part is done."],
			["Finish the bill", "Check it, Save, Submit. Then Print, or make the e-way bill if goods move by lorry."]],
		example: "Hosur shed order: 12,000 sq.ft PEB erection at ₹ 150 = ₹ 18 lakh (MS = Yes) and one extra gate ₹ 2 lakh (MS = No). Milestones: Foundation 30%, Structure 70%. When the foundation is done, the Foundation card makes a bill of ₹ 5.4 lakh (30% of ₹ 18 lakh). When the gate is fixed, “Non-MS bill” makes a bill of ₹ 2 lakh.",
		words: [["Sales order", "The customer’s full order with all its lines."], ["MS", "Milestone. MS = Yes lines are billed in parts by milestone."],
			["Non-MS bill", "A bill for lines with MS = No – not part of any milestone."], ["Area / Qty", "How much: square feet, square metres, numbers …"],
			["Cost per unit", "Price for one sq.ft / one sq.m / one piece."], ["Milestone", "One part of the work that you bill separately. All parts together make 100% of the MS work."],
			["Payment term", "One milestone line inside the order: “pay this % on this stage”."], ["Draft", "Saved but not final – you can still change it."],
			["Submit", "Make it final. After this it cannot be changed, only cancelled."], ["e-way bill", "A government slip needed when goods travel by lorry."]],
		links: [["so-new", "New sales order"], ["sales", "Bill a milestone"], ["sales-nonms", "Non-MS bill"], ["receive", "Record money received"]] },
	purchase: { title: "Purchase (orders and supplier bills)", where: "Purchase menu", color: "#7c3aed",
		intro: "Purchase works just like Sales, but for what you buy or give to a subcontractor. Write a purchase order, mark each line MS Yes or No, then enter the supplier’s bills by milestone or as non-MS bills. You can still buy straight from the BOQ.",
		steps: [["Make the purchase order", "Click Purchase → “New purchase order”. Choose the supplier, item code and GST. Write the lines: Sl. No., Description, Area, Unit, Cost per unit, and MS Yes / No."],
			["Milestones", "Give the milestones of the MS work (for example Fabrication 40%, Erection 60%). Create, check and Submit the order."],
			["Bill a milestone", "Purchase → “Bill a milestone” → the project. Click the stage the supplier has billed. The bill opens with the MS lines at that %. Type the supplier’s bill number, Save, Submit."],
			["Non-MS bill", "Purchase → “Non-MS bill” for the MS = No lines."],
			["Buy from the BOQ", "No order? Use “Purchase from BOQ”: project → stage → tick the items still to buy → Create purchase bill."],
			["Not in the BOQ?", "Use “Direct purchase bill”. It opens an empty bill already marked with the project and stage."]],
		example: "Subcontract order to Apvk Infra: 12,000 sq.ft erection at ₹ 40 (MS = Yes) and crane hire ₹ 60,000 (MS = No). After fabrication, click the “Fabrication 40%” card – a bill of ₹ 1.92 lakh opens. Type Apvk’s bill number, Save, Submit.",
		words: [["Supplier", "The shop, company or subcontractor you buy from."], ["Purchase order", "Your written order to the supplier."],
			["Purchase bill", "The supplier’s bill to you."], ["MS", "Milestone. MS = Yes lines are billed in parts."], ["Rate", "Price for one unit."]],
		links: [["po-new", "New purchase order"], ["po-bill", "Bill a milestone"], ["purchase", "Purchase from BOQ"], ["pay", "Record a payment to a supplier"]] },
	cash: { title: "Cash Flow (site cash)", where: "Cash Flow menu", color: "#d97706",
		intro: "Sites need cash for small daily costs. Here you write down cash given to a site and what the site spent, so you always know how much cash is still at the site.",
		steps: [["Give cash", "Click Cash Flow → “Give cash to site”. Choose the site, type the amount and the name of the person who received it, and click Save."],
			["Write an expense", "Click “Site expense”. Choose the site, what it was for (Transport, Equipment, Subcontract, Other), the amount, and who paid – site cash or office."],
			["Check the balance", "The site page shows Cash given – Spent = Cash still with the site."],
			["From Tally", "If the accounts team already entered cash payments in Tally, “Import from Tally” shows them. Tick them, choose the site and click Add."]],
		example: "You give ₹ 50,000 to Murugan at Hosur. He spends ₹ 6,500 on JCB and ₹ 3,000 on a lorry. The site page shows ₹ 40,500 still with the site.",
		words: [["Site cash", "Cash kept at the site for small expenses."], ["Expense", "Money spent."]],
		links: [["cash-give", "Give cash to site"], ["cash-expense", "Write a site expense"]] },
	bank: { title: "Bank (do this every day)", where: "Bank menu", color: "#0d9488",
		intro: "Every rupee that comes into or goes out of the bank should match a bill. This screen helps you check each bank entry one by one.",
		steps: [["Get the statement", "Open the bank’s net banking. Go to Account Statement, choose the dates and download it as Excel (not PDF). City Union Bank: Accounts → Account Statement → Format Excel."],
			["Upload it", "In Lite ERP click Bank → “Upload bank statement”, choose the account, and choose the file you downloaded. Do not change the file. Entries already uploaded are skipped."],
			["Check each entry", "Click Bank → “Daily bank check”. Money that came in (green) should match a sales bill. Money that went out (red) should match a purchase bill."],
			["Click the right bill", "The app shows likely bills in green boxes. Click the correct one. Done for that entry."],
			["No bill? Explain it", "Some entries have no bill, like a loan, salary or bank charges. Choose the reason from the list, type a short note, and click “Save remark”."]],
		example: "The bank shows “+ ₹ 34,69,200 from Ashok Leyland”. The app suggests bill SINV-0041 for ₹ 35,40,000 and says “less 2% (TDS)”. The customer kept 2% as tax (TDS), so this is the right bill. Click it.",
		words: [["Bank statement", "The bank’s list of all money in and out of your account."], ["TDS", "Tax the customer keeps back and pays to the government for you. So you receive a little less than the bill."],
			["Remark", "A short note explaining something."]],
		links: [["bank-upload", "Upload bank statement"], ["bank", "Daily bank check"]] },
	site: { title: "Site Summary", where: "Site Summary menu", color: "#2563eb",
		intro: "One table that shows, for every site, how much you billed, how much came in, and how much you spent.",
		steps: [["Open All sites", "Click Site Summary → “All sites”."],
			["Read one row", "Each row is one site. Billed = money asked from the customer. Received = money that came in. Spent = purchases plus site expenses."],
			["Watch the last column", "“Billed − spent” is like profit so far. Red means you have spent more than you billed."],
			["Click a site", "Click any row to see that site’s details and quick buttons."]],
		example: "Hosur: Billed ₹ 35 lakh, Spent ₹ 32 lakh, Billed − spent ₹ 3 lakh. The site is so far making a small profit.",
		words: [["Received", "Money that has actually come into the bank."], ["Spent", "Money paid out for this site."]],
		links: [["sites", "All sites"], ["cash-position", "Cash with each site"]] },
	me: { title: "My work (every employee)", where: "My work menu", color: "#c8102e",
		intro: "Your own attendance, leave and details in one place. Lite ERP opens by itself when you log in, and around office start and end time it takes you straight to the punch page.",
		steps: [["Punch every day", "Tap “Punch IN / OUT”. The first time, it asks you to take your face photo from the front, left and right. After that each punch takes a selfie with the time and GPS place."],
			["See your month", "“My attendance” shows each day: IN, OUT, hours and late. Tap a day to see each punch with photo and place."],
			["Could not punch?", "Use “Attendance request”: forgot to punch, on duty, client / site visit, travel, work from home, phone problem or other. Write where you were. HR approves it."],
			["Leave", "Use “Leave request”. You see how much leave is left. You can withdraw a request until HR approves it."],
			["Your details", "“My details” – change phone, address, bank or photo. The change happens only after HR approves."],
			["Password", "The first login uses SBI@2026. You must set your own password, then log in again with your user id and the new password."]],
		example: "On Monday you went straight to the Velachery site. Open “Attendance request”, choose “Client / Site Visit”, write “Velachery site – slab casting”, and send. When HR approves, Monday counts as present.",
		words: [["Attendance request", "Asking HR to mark you present for a day you could not punch."], ["Withdraw", "Take back a request before HR answers it."]],
		links: [["me", "My attendance"], ["punch", "Punch IN / OUT"], ["me-att", "Attendance request"], ["me-leave", "Leave request"]] },
	hr: { title: "HR (workers and staff)", where: "HR menu", color: "#16a34a",
		intro: "See who came to work – site workers (they punch with the site app) and office staff (they punch with the SBI Office app on their phone). Look at one day, the whole salary month, or any dates you choose.",
		steps: [["Open attendance", "Click HR → “Attendance”. It opens on today."],
			["Pick the period", "Click Day, This salary month, Last salary month, or Custom dates (choose From and To)."],
			["Set the salary month once", "Click “⚙ Month settings”. If salary is from the 1st to the last day, keep 1. If it is from the 26th to the 25th, type 26. Also set how many hours make a full day and a half day."],
			["Set the office place once", "In the same settings, stand inside the office and click “Use my current location”, then Save. Or open the SBI Office app and click “Set office here”. Also set office start / end time, grace minutes and the reminder."],
			["Office staff punch", "Each staff member opens the “SBI Office” app on their phone (add it to the home screen once) and taps Punch. The camera opens, they take a selfie, and the time and GPS location are saved. 15 minutes before office time they get a reminder."],
			["Check the office list", "The Office staff table shows IN time, OUT time and hours. Red “outside” means they punched away from the office. Click a name to see every punch with photo and map."],
			["Mark attendance and pay salary", "At month end, choose This salary month and click “Mark staff attendance from punches”. Then click “Run payroll” – the month dates fill in by themselves."],
			["HR dashboard", "HR → “HR dashboard” shows total employees, present, late, on leave and not punched today. Tap a box to filter, tap a name to see the month with every punch photo and GPS place, leave and requests."],
			["Add an employee and a login", "HR → “Add / edit employee”: Employee ID No., name, photo and dates. Tick “Give this employee a login”, type a user id (not e-mail) and tick the allowed areas. The password is SBI@2026 for the first login only."],
			["Approve requests", "HR → “Requests to approve” has three tabs: attendance requests, leave and detail changes. Approve, or write a remark and Reject."],
			["Letters", "HR → “Appointment order” or “Relieving order”, pick the employee, and print. For a relieving order first set Status = Left and the relieving date."]],
		example: "Salary month starts on the 26th. On 25 November choose “This salary month” (26 Oct – 25 Nov). Priya has 24 days, 2 of them half days. Click “Mark staff attendance from punches”, then “Run payroll for 26-10-2026 – 25-11-2026”.",
		words: [["Punch", "Marking IN or OUT with the phone (photo and location)."], ["Geofence / office area", "The allowed area around a site or the office. Punching outside it shows in red."],
			["Salary month", "The days one salary covers, for example 26th to 25th."], ["Full day / half day", "Enough hours between first IN and last OUT to count as a full or a half day."],
			["No OUT", "The person forgot to punch OUT – that day is not marked automatically."]],
		links: [["hr-dash", "HR dashboard"], ["hr", "Attendance"], ["hr-req", "Requests to approve"], ["ext:/sbi_office", "SBI Office punch app"], ["hr-settings", "Month & office settings"]] },
	gst: { title: "GST", where: "GST menu", color: "#c8102e",
		intro: "GST is a tax. You collect GST from customers on your bills and pay GST to suppliers on their bills. The difference is paid to the government.",
		steps: [["Open GST", "Click GST → “GST to pay”."],
			["Choose the period", "Pick This month, This quarter, This year or your own dates."],
			["Read the boxes", "Output GST = GST you collected on sales. Input credit = GST you paid on purchases. Net = Output minus Input."],
			["Balance to pay", "The last box shows how much GST you still owe the government. If it is green and says “carried forward”, you have extra credit."]],
		example: "This month you collected ₹ 5,00,000 GST on sales and paid ₹ 2,72,000 GST on purchases. So you owe ₹ 2,28,000 GST to the government.",
		words: [["Output GST", "GST you collected from customers."], ["Input credit (ITC)", "GST you paid to suppliers. It reduces the GST you have to pay."]],
		links: [["gst", "GST to pay"]] },
};
const HELP_ORDER = ["me", "home", "projects", "sales", "purchase", "cash", "bank", "site", "hr", "gst"];
const GLOSSARY = [
	["ERP", "Software that keeps all company records – bills, money, stock, workers – in one place."],
	["Company", "Shiv Bharat has two companies (two GST numbers). The box at the top right chooses which one you are looking at."],
	["Customer", "The person or company who pays you for the work."], ["Supplier", "The shop or company you buy from."],
	["Invoice / bill", "A paper asking someone to pay. Sales invoice = your bill to a customer. Purchase invoice = a supplier’s bill to you."],
	["Project", "One building job at one site."], ["Stage / milestone", "One part of a job, like Foundation or Roofing. Bills are often made per stage."],
	["BOQ", "Bill of Quantities – the list of items and quantities needed for the work."],
	["Draft", "Saved but not final. You can still change it."], ["Submit", "Make it final. After this it is counted in the accounts and cannot be changed."],
	["Outstanding", "Money still not paid."], ["Overdue", "Late – the last date to pay has passed."],
	["GST", "A tax added to bills. Output GST is collected from customers; input credit is GST paid to suppliers."],
	["TDS", "Tax a customer keeps back from your payment and pays to the government for you."],
	["Bank statement", "The bank’s list of all money in and out of the account."], ["Site cash", "Cash kept at a site for small daily expenses."],
];

function helpSteps(x) {
	return `<ol class="hsteps">${x.steps.map((s, i) => `<li><span class="hn" style="background:${x.color}">${i + 1}</span>
		<div><b>${esc(s[0])}</b><p>${esc(s[1])}</p></div></li>`).join("")}</ol>`;
}
function helpExtra(x) {
	let h = "";
	if (x.example) h += `<div class="hex"><div class="hex-t">${ICON("check")} Example</div><p>${esc(x.example)}</p></div>`;
	if (x.words && x.words.length) h += `<div class="hwords"><div class="hex-t">${ICON("info")} Words you will see</div>${x.words.map((w) =>
		`<div><b>${esc(w[0])}</b><span>${esc(w[1])}</span></div>`).join("")}</div>`;
	return h;
}

function viewHelp(focus) {
	S.here = () => viewHelp(focus);
	S.current = () => viewHelp(focus);
	setMenu("help");
	crumbs([["Help", null]]);
	let h = `<div class="hhero"><div><div class="hh-t">${ICON("info")} Learn Lite ERP</div>
			<div class="hh-s">Simple steps for every screen, with examples. No computer or accounts knowledge needed.</div></div>
			<input class="hsearch" id="hsearch" placeholder="Search – e.g. bank, BOQ, GST, cash" autocomplete="off"></div>
		<div class="hstart"><div class="hs-t">${ICON("home")} Start here – what is Lite ERP?</div>
			<p>Think of Lite ERP as the <b>company’s notebook on the computer</b>. Every bill, every payment, every bag of cement bought and every worker’s attendance is written in it. Because everything is written in one place, it can add things up for you and show you the answers.</p>
			<div class="hs-rules">
				<div><span>1</span><p><b>The red bar at the top is the menu.</b> Move the mouse on a word (like “Bank”) to see its choices. Click a choice.</p></div>
				<div><span>2</span><p><b>The screen changes below the red bar.</b> You never leave this page. The line under the red bar shows where you are – click a word there to go back.</p></div>
				<div><span>3</span><p><b>Save, then Submit.</b> Save keeps your work as a draft (can still change). Submit makes it final.</p></div>
				<div><span>4</span><p><b>Red = please look.</b> Red numbers mean something is late or missing.</p></div>
				<div><span>5</span><p><b>Stuck?</b> Click “How this works” at the top right of any screen to see its steps.</p></div>
			</div></div>
		<div class="hday"><div class="hday-t">${ICON("calendar")} Your work every day (about 15 minutes)</div><div class="hday-g">
			<a data-go="bank-upload" data-m="bank"><span>1</span>Upload the bank statement and check each entry</a>
			<a data-go="purchase" data-m="purchase"><span>2</span>Enter supplier bills for the right project and stage</a>
			<a data-go="cash-give" data-m="cash"><span>3</span>Write cash given to sites and site expenses</a>
			<a data-go="home" data-m="home"><span>4</span>Look at Home – anything in red?</a></div></div>
		<div class="hgrid" id="hgrid">`;
	HELP_ORDER.forEach((k) => {
		const x = HELP[k];
		const words = (x.title + " " + x.intro + " " + x.steps.map((s) => s.join(" ")).join(" ") + " " + (x.example || "") + " " +
			(x.words || []).map((w) => w.join(" ")).join(" ")).toLowerCase();
		h += `<div class="hcard ${focus === k ? "focus" : ""}" id="help-${k}" data-s="${esc(words)}" style="--hc:${x.color}">
			<div class="hc-top"><span class="hc-ic" style="background:${x.color}">${ICON(MENU_ICON[k] || "home")}</span>
				<div><div class="hc-t">${esc(x.title)}</div><div class="hc-w">${esc(x.where)}</div></div></div>
			<div class="hc-i">${esc(x.intro)}</div>${helpSteps(x)}${helpExtra(x)}
			<div class="bar">${x.links.map((g) => `<a class="qa-i" data-go="${g[0]}" data-m="${k}">${esc(g[1])} →</a>`).join("")}</div></div>`;
	});
	h += `</div><div class="hint" id="hnone" style="display:none">Nothing found. Try another word.</div>
		<div class="box hgloss" id="hgloss"><h3>${ICON("info")} Words you will see – in simple language</h3><div class="hg-g">${GLOSSARY.map((g) =>
			`<div class="hg-i" data-s="${esc((g[0] + " " + g[1]).toLowerCase())}"><b>${esc(g[0])}</b><span>${esc(g[1])}</span></div>`).join("")}</div></div>`;
	showView(h);
	const s = q("#hsearch");
	s.addEventListener("input", () => {
		const t = s.value.toLowerCase().trim();
		let n = 0;
		R.querySelectorAll(".hcard, .hg-i").forEach((c) => { const ok = !t || c.dataset.s.indexOf(t) >= 0; c.classList.toggle("hide", !ok); if (ok) n++; });
		q("#hnone").style.display = n ? "none" : "block";
	});
	if (focus && q("#help-" + focus)) setTimeout(() => q("#help-" + focus).scrollIntoView({ behavior: "smooth", block: "start" }), 80);
}

// slide-in help for the screen you are on
function helpDrawer(key) {
	key = HELP[key] ? key : (HELP[S.menu] ? S.menu : "home");
	const x = HELP[key];
	let d = q("#hdrawer");
	if (!d) {
		q("#lx").insertAdjacentHTML("beforeend", `<div class="hshade" id="hshade" data-act="help-close"></div><aside class="hdrawer" id="hdrawer"></aside>`);
		d = q("#hdrawer");
	}
	d.innerHTML = `<div class="hd-head" style="background:${x.color}"><span class="hc-ic">${ICON(MENU_ICON[key] || "home")}</span>
			<div><div class="hd-t">${esc(x.title)}</div><div class="hd-w">${esc(x.where)}</div></div>
			<button class="hd-x" data-act="help-close" title="Close">×</button></div>
		<div class="hd-body"><div class="hc-i">${esc(x.intro)}</div>${helpSteps(x)}${helpExtra(x)}
			<div class="bar">${x.links.map((g) => `<a class="qa-i" data-go="${g[0]}" data-m="${key}">${esc(g[1])} →</a>`).join("")}</div>
			<a class="hd-all" data-go="help" data-m="help">All help topics and word meanings</a></div>`;
	requestAnimationFrame(() => q("#lx").classList.add("hd-open"));
}
function helpClose() { const lx = q("#lx"); if (lx) lx.classList.remove("hd-open"); }

// ------------------------------------------------------------------ phone menu (one list instead of the top row)
function drawPhoneMenu() {
	const p = q("#mnav");
	if (!p) return;
	p.innerHTML = `<a class="mn-home" data-go="home" data-m="home">${ICON("home")} Home</a>` + MENUS.map((m) => `
		<div class="mn-sec"><div class="mn-h">${ICON(MENU_ICON[m.id] || "info")} ${esc(m.label)}<a class="mn-q" data-act="help-drawer" data-h="${m.id}">?</a></div>
		${m.items.map((i) => `<a data-go="${esc(i[0])}" data-m="${m.id}">${esc(i[1])}</a>`).join("")}</div>`).join("") +
		`<a class="mn-home" data-go="help" data-m="help">${ICON("info")} Help</a>`;
}

// ------------------------------------------------------------------ unsaved BOQ guard
function boqDirty() {
	return !!(S.boqEd && S.boqEd.dirty && q(".boqg"));
}
function leaveGuard(fn) {
	if (!boqDirty()) { fn(); return; }
	frappe.confirm(__("You have unsaved BOQ changes. Leave without saving?"), () => { S.boqEd.dirty = false; fn(); });
}
document.addEventListener("keydown", (e) => { if (e.key === "Escape") helpClose(); });
window.addEventListener("beforeunload", (e) => { if (boqDirty()) { e.preventDefault(); e.returnValue = ""; } });

// ------------------------------------------------------------------ events
R.addEventListener("click", async (e) => {
	const m = e.target.closest(".m-btn");
	if (m && window.matchMedia("(hover: none)").matches && m.parentElement.querySelector(".m-sub")) {
		// touch screens: first tap opens the submenu
		const box = m.parentElement;
		if (!box.classList.contains("open")) { R.querySelectorAll(".m.open").forEach((x) => x.classList.remove("open")); box.classList.add("open"); return; }
	}
	const g = e.target.closest("[data-go]");
	if (g) {
		e.preventDefault();
		R.querySelectorAll(".m.open").forEach((x) => x.classList.remove("open"));
		q("#lx").classList.remove("mn-open");
		leaveGuard(() => go(g.dataset.go, g.dataset.m || S.menu));
		return;
	}
	if (e.target.closest("#burger")) { q("#lx").classList.toggle("mn-open"); return; }
	if (q("#lx").classList.contains("mn-open") && !e.target.closest("#mnav")) q("#lx").classList.remove("mn-open");
	const c = e.target.closest("[data-crumb]");
	if (c) { const fn = S.crumbs[Number(c.dataset.crumb)][1]; if (fn) leaveGuard(fn); return; }
	if (e.target.closest(".newstage") && !e.target.closest("[data-act]")) return;
	const pick = e.target.closest("[data-pick]");
	if (pick) { if (S.onPick) S.onPick(findProject(pick.dataset.pick)); return; }
	const el = e.target.closest("[data-act]");
	if (!el) return;
	const a = el.dataset.act;
	if (a !== "open" && el.tagName === "A") e.preventDefault();
	if (a === "open") {
		e.preventDefault(); e.stopPropagation();
		const last = S.crumbs[S.crumbs.length - 1] || ["Back", null];
		frameForm(el.dataset.dt, el.dataset.name, S.crumbs.slice(0, -1).concat([[last[0], S.here || null]]));
	}
	else if (a === "newtab") {
		let url = BASE;
		try { url = q("#frame").contentWindow.location.href; } catch (x) { /* ignore */ }
		window.open(url, "_blank");
	}
	else if (a === "go") go(el.dataset.go, S.menu);
	else if (a === "o-bill") orderBill(el, "ms_bill");
	else if (a === "o-nonms") orderBill(el, "nonms_bill");
	else if (a === "o-new") viewOrderForm(findProject(el.dataset.p), el.dataset.kind);
	else if (a === "o-mode") viewOrders(findProject(el.dataset.p), el.dataset.kind, el.dataset.mode);
	else if (a === "o-save") orderSave(el);
	else if (a === "ol-add") { olRead(); const l = olBlank(); l.sl = String(S.ms.lines.length + 1); S.ms.lines.push(l); olRender(); }
	else if (a === "ol-del") { olRead(); S.ms.lines.splice(Number(el.dataset.i), 1); olRender(); }
	else if (a === "ol-boq") olFromBoq();
	else if (a === "p-so") viewOrderForm(findProject(el.dataset.p), "sales");
	else if (a === "p-po") viewOrderForm(findProject(el.dataset.p), "purchase");
	else if (a === "direct-si") directSales(findProject(el.dataset.p));
	else if (a === "ms-preset") msPreset(el.dataset.k);
	else if (a === "ms-import") msImport(Number(el.dataset.i));
	else if (a === "ms-add") { msRead(); S.ms.rows.push({ name: "", percent: Math.max(0, Math.round((100 - msTotals()) * 100) / 100), due_date: frappe.datetime.add_days(frappe.datetime.get_today(), 30 * (S.ms.rows.length + 1)) }); msRender(); }
	else if (a === "ms-del") { msRead(); S.ms.rows.splice(Number(el.dataset.i), 1); msRender(); }
	else if (a === "boq") { e.stopPropagation(); viewBoq(findProject(el.dataset.p), el.dataset.stage); }
	else if (a === "direct-pi") { e.stopPropagation(); directPurchase(findProject(el.dataset.p), el.dataset.stage, true); }
	else if (a === "make-pi") makePurchaseFromBoq();
	else if (a === "project") viewProject(el.dataset.p);
	else if (a === "p-bill") viewMilestones(findProject(el.dataset.p));
	else if (a === "p-buy") viewStages(findProject(el.dataset.p), false);
	else if (a === "p-cash") viewCash(findProject(el.dataset.p), "give");
	else if (a === "hr-site") viewHrSite(el.dataset.p);
	else if (a === "hr-today") viewHr(frappe.datetime.get_today());
	else if (a === "hr-mode") { const P = S.hrP || {}; S.hrP = { mode: el.dataset.mode, day: P.day || frappe.datetime.get_today(), from: P.from, to: P.to };
		if (el.dataset.mode === "custom" && !(P.from && P.to)) { const m = salaryMonth((S.hrSet || {}).start_day, frappe.datetime.get_today(), 0); S.hrP.from = m[0]; S.hrP.to = frappe.datetime.get_today(); }
		viewHr(); }
	else if (a === "hr-emp") viewHrEmp(el.dataset.e);
	else if (a === "m-day") { const r = R.querySelector(`.mpun[data-day="${el.dataset.i}"]`); if (r) r.classList.toggle("hide"); }
	else if (a === "m-back") { S.mBack = Number(el.dataset.b) || 0; if (S.current) S.current(); }
	else if (a === "ar-save") {
		const rs = R.querySelector('input[name="ar-reason"]:checked');
		if (!val("#ar-exp")) { frappe.msgprint(__("Write the details: where you were and what work.")); return; }
		el.disabled = true;
		try {
			await call("me_att_req", { from_date: val("#ar-from"), to_date: val("#ar-to") || val("#ar-from"), half_day: q("#ar-half").checked ? 1 : 0,
				reason: rs ? rs.value : "On Duty", explanation: val("#ar-exp") });
			frappe.show_alert({ message: __("Sent to HR"), indicator: "green" });
			viewMeAtt();
		} catch (x) { el.disabled = false; }
	}
	else if (a === "lv-save") {
		el.disabled = true;
		try {
			await call("me_leave_req", { leave_type: val("#lv-type"), from_date: val("#lv-from"), to_date: val("#lv-to") || val("#lv-from"),
				half_day: q("#lv-half").checked ? 1 : 0, description: val("#lv-desc") });
			frappe.show_alert({ message: __("Leave sent to HR"), indicator: "green" });
			viewMeLeave();
		} catch (x) { el.disabled = false; }
	}
	else if (a === "me-withdraw") {
		frappe.confirm(__("Withdraw this request?"), async () => {
			await call("me_cancel_req", { kind: el.dataset.k, name: el.dataset.n });
			S.mData = null;
			if (S.current) S.current();
		});
	}
	else if (a === "me-prof-save") {
		const vals = {};
		R.querySelectorAll("#view [data-f]").forEach((x) => { if (x.value !== (S.meOrig || {})[x.dataset.f]) vals[x.dataset.f] = x.value; });
		if (!Object.keys(vals).length && !S.meNewPhoto) { frappe.msgprint(__("Nothing was changed.")); return; }
		el.disabled = true;
		try {
			await call("me_profile_save", { values: JSON.stringify(vals), photo: S.meNewPhoto || "" });
			frappe.msgprint({ title: __("Sent to HR"), indicator: "green", message: __("Your details change after HR approves.") });
			S.mData = null;
			viewMe();
		} catch (x) { el.disabled = false; }
	}
	else if (a === "pw-save") pwSave(el);
	else if (a === "hd-filter") { S.hdFilter = el.dataset.f; hdList(); }
	else if (a === "emp-month") { e.stopPropagation(); S.mBack = 0; viewEmpMonth(el.dataset.e); }
	else if (a === "emp-edit") { e.stopPropagation(); viewEmpForm(el.dataset.e); }
	else if (a === "emp-new") viewEmpForm("");
	else if (a === "emp-save") empSave(el);
	else if (a === "req-tab") viewReqs(el.dataset.t);
	else if (a === "req-do") reqDo(el);
	else if (a === "pe-pick") { if (S.onEmp) S.onEmp(el.dataset.e); }
	else if (a === "letter") openLetter(el.dataset.f, el.dataset.e);
	else if (a === "hr-office-all") { const b = R.querySelector('[data-act="hr-emp"]'); if (b) b.scrollIntoView({ behavior: "smooth", block: "center" }); }
	else if (a === "hr-settings") viewHrSettings();
	else if (a === "hr-back") viewHr();
	else if (a === "hs-save") hsSave(el);
	else if (a === "hs-here") hsHere();
	else if (a === "hr-mark") hrMark(el);
	else if (a === "hr-payroll") frameNew("Payroll Entry", { company: S.company, start_date: el.dataset.f, end_date: el.dataset.t, posting_date: el.dataset.t > frappe.datetime.get_today() ? frappe.datetime.get_today() : el.dataset.t, payroll_frequency: "Monthly" }, null, [["HR", () => viewHr()]]);
	else if (a === "desk") window.location.href = BASE;
	else if (a === "bank-up") { e.stopPropagation(); viewBankUpload(el.dataset.acc); }
	else if (a === "bank-chk") { e.stopPropagation(); viewBankCheck(el.dataset.acc, "check"); }
	else if (a === "bk-show") viewBankCheck(S.bankAcc, el.dataset.show);
	else if (a === "bu-save") buSave(el);
	else if (a === "bu-sample") downloadSample(el.dataset.acc);
	else if (a === "help-drawer") { R.querySelectorAll(".m.open").forEach((x) => x.classList.remove("open")); el.blur && el.blur(); helpDrawer(el.dataset.h || S.menu); }
	else if (a === "help-close") helpClose();
	else if (a === "boq-edit") viewBoqEdit(findProject(el.dataset.p), el.dataset.stage);
	else if (a === "boq-newstage") { e.stopPropagation(); boqNewStage(el); }
	else if (a === "boq-add") { const b = S.boqEd; b.rows.push(boqBlank(b.rows.length + 1)); b.dirty = true; boqRender();
		const ins = R.querySelectorAll('input[data-f="description"]'); if (ins.length) ins[ins.length - 1].focus(); }
	else if (a === "boq-del") { const b = S.boqEd; b.rows.splice(Number(el.dataset.i), 1); b.dirty = true; boqRender(); }
	else if (a === "boq-save") boqSave(el);
	else if (a === "boq-sample") boqSample();
	else if (a === "bk-match") { el.disabled = true; bankSet({ txn: el.dataset.txn, status: "Matched", doctype: el.dataset.dt, name: el.dataset.name }).catch(() => (el.disabled = false)); }
	else if (a === "bk-other") {
		const inv = (R.querySelector(`.bk-inv[data-txn="${CSS.escape(el.dataset.txn)}"]`) || {}).value || "";
		if (!inv.trim()) { frappe.msgprint(__("Type the sales or purchase invoice number.")); return; }
		bankSet({ txn: el.dataset.txn, status: "Matched", name: inv.trim() });
	}
	else if (a === "bk-noinv") {
		const t = CSS.escape(el.dataset.txn);
		const rsn = (R.querySelector(`.bk-rsn[data-txn="${t}"]`) || {}).value || "";
		const rem = (R.querySelector(`.bk-rem[data-txn="${t}"]`) || {}).value || "";
		if (!rsn) { frappe.msgprint(__("Choose why there is no invoice.")); return; }
		if (!rem.trim()) { frappe.msgprint(__("Write a remark saying what this entry is.")); return; }
		bankSet({ txn: el.dataset.txn, status: "No Invoice", reason: rsn, remarks: rem.trim() });
	}
	else if (a === "bk-undo") bankSet({ txn: el.dataset.txn, status: "" });
	else if (a === "add-cash" || a === "add-expense") {
		const p = findProject(el.dataset.p);
		const v = (s) => (q(s) || {}).value || "";
		const args = a === "add-cash"
			? { project: p.name, date: v("#c-date"), amount: v("#c-amount"), received_by: v("#c-who"), remarks: v("#c-remarks") }
			: { project: p.name, date: v("#e-date"), amount: v("#e-amount"), category: v("#e-cat"), payment_source: v("#e-src"), party: v("#e-party"), description: v("#e-desc") };
		el.disabled = true;
		try {
			const r = await call(a === "add-cash" ? "add_cash" : "add_expense", args);
			frappe.show_alert({ message: __("Saved {0}", [r.name]), indicator: "green" });
			viewCash(p, a === "add-cash" ? "give" : "expense");
		} catch (x) { el.disabled = false; }
	}
	else if (a === "import-tally") {
		const prj = (q("#t-project") || {}).value;
		const picks = Array.from(R.querySelectorAll(".t-pick:checked")).map((x) => x.dataset.je);
		if (!picks.length) { frappe.msgprint(__("Tick the Tally payments to add.")); return; }
		if (!prj) { frappe.msgprint(__("Pick the site these payments belong to.")); return; }
		const kinds = picks.map((je) => { const s = R.querySelector(`.t-kind[data-je="${CSS.escape(je)}"]`); return s ? s.value : "Cash"; });
		el.disabled = true;
		try {
			const r = await call("import_tally", { jes: picks.join(","), kinds: kinds.join(","), projects: picks.map(() => prj).join(",") });
			frappe.show_alert({ message: __("{0} added, {1} skipped", [(r.made || []).length, r.skipped || 0]), indicator: "green" });
			viewTally();
		} catch (x) { el.disabled = false; }
	}
});

R.addEventListener("change", (e) => {
	const id = e.target.id;
	if (id === "company") {
		S.company = e.target.value;
		try { localStorage.setItem("lite_erp_company", S.company); } catch (x) { /* ignore */ }
		S.summary = null;
		if (S.current) S.current();
	}
	else if (id === "period") {
		S.period = e.target.value;
		if (S.period === "custom") { q("#pcustom").classList.remove("hide"); return; }
		if (S.current) S.current();
	}
	else if (id === "pfrom" || id === "pto") {
		S.from = (q("#pfrom") || {}).value; S.to = (q("#pto") || {}).value;
		if (S.from && S.to && S.current) S.current();
	}
	else if (id === "t-bank") { S.includeBank = e.target.checked; viewTally(); }
	else if (id === "hr-date") { if (e.target.value) viewHr(e.target.value); }
	else if (id === "hr-from" || id === "hr-to") { const f = q("#hr-from").value, t = q("#hr-to").value; if (f && t) { S.hrP = { mode: "custom", from: f, to: t, day: (S.hrP || {}).day }; viewHr(); } }
	else if (id === "hs-start") hsExample();
	else if (id === "ef-login") { const b = q("#ef-login-box"); if (b) b.classList.toggle("hide", !e.target.checked); }
	else if (id === "pw-show") ["#pw1", "#pw2"].forEach((s) => { const x = q(s); if (x) x.type = e.target.checked ? "text" : "password"; });
	else if ((id === "ef-photo" || id === "me-photo") && e.target.files && e.target.files[0]) {
		fileToJpeg(e.target.files[0], 900).then((u) => {
			if (id === "ef-photo") { S.empPhoto = u; const p = q("#ef-prev"); p.src = u; p.classList.remove("hide"); const n = q("#ef-noph"); if (n) n.classList.add("hide"); }
			else { S.meNewPhoto = u; const p = q("#me-photo-prev"); p.src = u; p.classList.remove("hide"); }
		}).catch((x) => frappe.msgprint(x.message));
	}
	else if (id === "bu-file") { if (e.target.files && e.target.files[0]) buFile(e.target.files[0]); }
	else if (id === "boq-file") { if (e.target.files && e.target.files[0]) boqFile(e.target.files[0]); e.target.value = ""; }
	else if (id === "bu-hi") { const v = Math.max(1, Number(e.target.value || 1)) - 1; S.bu.hi = v; S.bu.map = guessMap(S.bu.raw[v] || []); buRender(); }
	else if (e.target.classList.contains("bu-map")) { S.bu.map[e.target.dataset.f] = Number(e.target.value); buRender(); }
	else if (id === "bk-acc") viewBankCheck(e.target.value, S.bankShow);
	else if (id === "bk-show") viewBankCheck(S.bankAcc, e.target.value);
	else if (id === "t-all") R.querySelectorAll(".t-pick").forEach((x) => (x.checked = e.target.checked));
	else if (id === "b-all") { R.querySelectorAll(".b-pick").forEach((x) => { if (!x.closest("details")) x.checked = e.target.checked; }); boqTotal(); }
	else if (e.target.classList.contains("b-pick")) boqTotal();
});
R.addEventListener("dragover", (e) => { const d = e.target.closest && e.target.closest(".drop"); if (d) { e.preventDefault(); d.classList.add("over"); } });
R.addEventListener("dragleave", (e) => { const d = e.target.closest && e.target.closest(".drop"); if (d) d.classList.remove("over"); });
R.addEventListener("drop", (e) => {
	const d = e.target.closest && e.target.closest(".drop");
	if (!d) return;
	e.preventDefault();
	d.classList.remove("over");
	if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) buFile(e.dataTransfer.files[0]);
});
R.addEventListener("input", (e) => {
	if (e.target.id === "hd-q") { hdList(); return; }
	if (e.target.id === "pe-q") { peList(); return; }
	if (e.target.classList && e.target.classList.contains("bg")) { boqInput(e.target); return; }
	if (e.target.classList.contains("b-qty") || e.target.classList.contains("b-rate")) boqTotal();
	if (e.target.classList.contains("ms-p")) msTotals();
	if (e.target.classList.contains("ol-in")) olTotals();
});

// ------------------------------------------------------------------ full-screen layout
// Lite ERP fills the screen beside the desk's own icon rail / top bar.
function deskEdges() {
	const host = R.host;
	const at = (x, y) => (document.elementsFromPoint(x, y) || []).filter((el) =>
		el !== host && !host.contains(el) && el !== document.body && el !== document.documentElement);
	let L = 0, T = 0;
	at(2, Math.round(window.innerHeight / 2)).forEach((el) => {
		const r = el.getBoundingClientRect();
		if (r.left <= 2 && r.width < 260 && r.height > window.innerHeight * 0.5) L = Math.max(L, r.right);
	});
	at(Math.round(window.innerWidth / 2), 2).forEach((el) => {
		const r = el.getBoundingClientRect();
		const pos = getComputedStyle(el).position;
		const bar = pos === "fixed" || pos === "sticky" || el.tagName === "HEADER" || el.classList.contains("navbar");
		if (bar && r.top <= 2 && r.height > 20 && r.height < 90 && r.width > window.innerWidth * 0.5) T = Math.max(T, r.bottom);
	});
	return { L: Math.round(L), T: Math.round(T) };
}

function fit() {
	const lx = q("#lx");
	if (!lx) return;
	const on = /^\/(desk|app)\/lite-erp/.test(window.location.pathname);
	if (on) {
		const e = deskEdges();
		lx.classList.add("full");
		Object.assign(lx.style, { top: e.T + "px", left: e.L + "px", right: "0px", bottom: "0px", height: "auto" });
		document.body.style.overflow = "hidden";
		// a transformed parent would break fixed positioning: fall back to a tall box
		const r = lx.getBoundingClientRect();
		if (Math.abs(r.left - e.L) > 4 || Math.abs(r.top - e.T) > 4) {
			lx.classList.remove("full");
			Object.assign(lx.style, { top: "", left: "", right: "", bottom: "" });
			lx.style.height = Math.max(480, window.innerHeight - Math.max(lx.getBoundingClientRect().top, 0) - 8) + "px";
		}
	} else {
		document.body.style.overflow = "";
	}
}
function outerChrome() {
	if (!document.getElementById("lx-outer-css")) {
		const st = document.createElement("style");
		st.id = "lx-outer-css";
		st.textContent = `body.lx-on .page-head, body.lx-on .layout-side-section { display: none !important; }
			body.lx-on .page-body, body.lx-on .container.page-body { max-width: 100% !important; width: 100% !important; padding-left: 8px !important; padding-right: 8px !important; }
			body.lx-on .layout-main-section-wrapper, body.lx-on .layout-main-section { padding: 0 !important; margin: 0 !important; }
			body.lx-on .custom-block-widget-box, body.lx-on .widget.custom-block-widget-box { padding: 0 !important; border: 0 !important; background: none !important; }
			body.lx-on .codex-editor__redactor { padding-bottom: 0 !important; }`;
		document.head.appendChild(st);
	}
	const check = () => {
		const on = /^\/(desk|app)\/lite-erp/.test(window.location.pathname);
		document.body.classList.toggle("lx-on", on);
		if (on) { setTimeout(fit, 50); setTimeout(fit, 500); } else document.body.style.overflow = "";
	};
	check();
	if (frappe.router && frappe.router.on && !window.__lx_router) { window.__lx_router = 1; frappe.router.on("change", check); }
	window.addEventListener("popstate", check);
}

// ------------------------------------------------------------------ start
outerChrome();
// follow the desk's light / dark theme
function syncTheme() { const lx = q("#lx"); if (lx) lx.classList.toggle("dark", document.documentElement.getAttribute("data-theme") === "dark"); }
syncTheme();
try { new MutationObserver(syncTheme).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] }); } catch (e) { /* ignore */ }
window.addEventListener("resize", fit);
q("#frame").addEventListener("load", () => { frameStyle(); setTimeout(frameStyle, 800); });
drawMenu();
drawPhoneMenu();
call("init").then((d) => {
	S.scope = d.scope || "all";
	S.areas = d.areas || [];
	S.me = d.me || null;
	if (!S.me) { const mi = MENUS.findIndex((m) => m.id === "me"); if (mi >= 0) MENUS.splice(mi, 1); const hi = HELP_ORDER.indexOf("me"); if (hi >= 0) HELP_ORDER.splice(hi, 1); }
	if (S.scope !== "all") {
		// limited login (HR, staff, sales…): keep only the menus this login may use
		for (let i = MENUS.length - 1; i >= 0; i--) if (S.areas.indexOf(MENUS[i].id) < 0) MENUS.splice(i, 1);
		for (let i = HELP_ORDER.length - 1; i >= 0; i--) if (S.areas.indexOf(HELP_ORDER[i]) < 0) HELP_ORDER.splice(i, 1);
		S.homeMenu = S.areas.indexOf("hr") >= 0 ? "hr" : S.me ? "me" : (MENUS[0] || { id: "me" }).id;
		S.homeKey = S.homeMenu === "hr" ? "hr-dash" : S.homeMenu === "me" ? "me" : ((MENUS[0] || { items: [["me"]] }).items[0][0]);
	}
	drawMenu();
	drawPhoneMenu();
	if (d.must_change) { viewChangePw(true); return; }
	// around office start / end time, staff land on the punch page
	if (d.punch_window && S.me) {
		const k = "sbi_punch_auto_" + frappe.datetime.get_today() + "_" + d.punch_window;
		let seen = "";
		try { seen = sessionStorage.getItem(k) || ""; } catch (x) { /* ignore */ }
		if (!seen) {
			try { sessionStorage.setItem(k, "1"); } catch (x) { /* ignore */ }
			window.location.href = "/sbi_office";
			return;
		}
	}
	S.companies = d.companies || [];
	S.projects = d.projects || [];
	const logo = (frappe.boot && frappe.boot.app_logo_url) || d.logo || "";
	const img = q("#lx-logo");
	if (logo && img) { img.onerror = () => img.classList.add("hide"); img.src = logo; img.classList.remove("hide"); }
	let saved = "";
	try { saved = localStorage.getItem("lite_erp_company") || ""; } catch (x) { /* ignore */ }
	const def = (saved && S.companies.indexOf(saved) >= 0 && saved) || frappe.defaults.get_user_default("Company") || d.default_company || S.companies[0] || "";
	q("#company").innerHTML = S.companies.map((c) => `<option value="${esc(c)}">${esc(c)}</option>`).join("");
	S.company = def;
	if (def) q("#company").value = def;
	go("home", "home");
	setTimeout(fit, 60);
	setTimeout(fit, 600);
	setTimeout(fit, 1500);
	// warm up the form area so the first invoice opens quickly
	setTimeout(() => { if (!q("#frame").getAttribute("src")) q("#frame").setAttribute("src", BASE + (S.scope === "all" ? "/sales-invoice" : "/employee")); }, 2500);
});
