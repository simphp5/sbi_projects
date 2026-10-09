// Copyright (c) 2026, Velmaska and contributors
frappe.pages["tally-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Tally Dashboard"), single_column: true });
	const dash = new TallyDashboard(page);
	wrapper.tally_dashboard = dash;
	dash.refresh();
};

frappe.pages["tally-dashboard"].on_page_show = function (wrapper) {
	if (wrapper.tally_dashboard) wrapper.tally_dashboard.refresh();
};

class TallyDashboard {
	constructor(page) {
		this.page = page;
		this.from = page.add_field({ fieldname: "from_date", label: __("From"), fieldtype: "Date",
			change: () => this.refresh() });
		this.to = page.add_field({ fieldname: "to_date", label: __("To"), fieldtype: "Date",
			default: frappe.datetime.get_today(), change: () => this.refresh() });
		page.set_primary_action(__("Refresh"), () => this.refresh(), "refresh");
		page.add_inner_button(__("Tally Settings"), () => frappe.set_route("Form", "Tally Settings"));
		page.add_inner_button(__("Sync Log"), () => frappe.set_route("List", "Tally Sync Log"));
		this.$body = $(`<div class="tally-dash"></div>`).appendTo(page.main);
		this.inject_css();
	}

	refresh() {
		frappe.call({
			method: "sbi_projects.tally.dashboard.get_dashboard",
			args: { from_date: this.from.get_value(), to_date: this.to.get_value() },
		}).then((r) => {
			const d = r.message || {};
			if (!this.from.get_value() && d.from_date) this.from.set_value(d.from_date);
			this.render(d);
		});
	}

	// ------------------------------------------------------------ helpers
	money(v) {
		return format_currency(v || 0, frappe.defaults.get_default("currency") || "INR", 0);
	}
	esc(v) {
		return frappe.utils.escape_html(v == null ? "" : String(v));
	}
	link(route, text) {
		return `<a href="/app/${route}">${this.esc(text)}</a>`;
	}
	tile(label, value, sub, colour, route) {
		const inner = `<div class="td-tile ${colour || ""}">
			<div class="td-label">${label}</div>
			<div class="td-value">${value}</div>
			${sub ? `<div class="td-sub">${sub}</div>` : ""}</div>`;
		return route ? `<a class="td-tile-link" href="/app/${route}">${inner}</a>` : inner;
	}
	card(title, body, extra) {
		return `<div class="td-card"><div class="td-card-head"><span>${title}</span>${extra || ""}</div>${body}</div>`;
	}
	table(cols, rows, empty) {
		if (!rows.length) return `<div class="td-empty">${empty || __("Nothing to show")}</div>`;
		return `<table class="td-table"><thead><tr>${cols.map((c) =>
			`<th class="${c.num ? "num" : ""}">${c.label}</th>`).join("")}</tr></thead><tbody>${rows.map((r) =>
			`<tr>${cols.map((c) => `<td class="${c.num ? "num" : ""}">${c.get(r)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
	}

	// ------------------------------------------------------------ render
	render(d) {
		const h = d.health || {};
		const v = d.vouchers || { by_type: [], by_month: [], recent: [], count: 0, amount: 0 };
		const m = d.masters || {};
		const rec = d.receivable || { total: 0, top: [] };
		const pay = d.payable || { total: 0, top: [] };
		const cb = d.cash_bank || [];
		const failed = d.failed || [];
		const skipped = d.skipped || [];
		const cbTotal = cb.reduce((a, r) => a + (r.bal || 0), 0);

		const ago = h.seconds_ago == null ? __("never")
			: h.seconds_ago < 90 ? __("{0} s ago", [Math.round(h.seconds_ago)])
			: h.seconds_ago < 5400 ? __("{0} min ago", [Math.round(h.seconds_ago / 60)])
			: __("{0} h ago", [Math.round(h.seconds_ago / 3600)]);
		const pill = (ok, yes, no) => `<span class="indicator-pill ${ok ? "green" : "red"}">${ok ? yes : no}</span>`;

		const health = `<div class="td-health">
			${pill(h.online, __("Agent online"), __("Agent offline"))}
			${pill(h.tally_reachable, __("Tally company open"), __("Tally not ready"))}
			${h.enabled ? "" : `<span class="indicator-pill orange">${__("Sync disabled")}</span>`}
			<span class="text-muted">${__("Agent last seen")} ${ago}</span>
			${h.last_sync_on ? `<span class="text-muted">· ${__("Last complete sync")} ${frappe.datetime.str_to_user(h.last_sync_on)}</span>` : ""}
			${h.last_error ? `<div class="td-error">${this.esc(h.last_error)}</div>` : ""}
		</div>`;

		const tiles = `<div class="td-tiles">
			${this.tile(__("Tally vouchers in period"), v.count, this.money(v.amount), "blue",
				'journal-entry?tally_voucher=["is","set"]')}
			${this.tile(__("Receivable (Tally customers)"), this.money(rec.total), __("as on {0}", [frappe.datetime.str_to_user(d.to_date)]), "green",
				"query-report/Accounts Receivable")}
			${this.tile(__("Payable (Tally suppliers)"), this.money(pay.total), __("as on {0}", [frappe.datetime.str_to_user(d.to_date)]), "orange",
				"query-report/Accounts Payable")}
			${this.tile(__("Bank + Cash"), this.money(cbTotal), __("{0} accounts", [cb.length]), "purple")}
			${this.tile(__("Failed records"), failed.length, failed.length ? __("needs attention") : __("all good"),
				failed.length ? "red" : "grey", "tally-sync-log?status=Failed")}
			${this.tile(__("Skipped as duplicates"), skipped.length, __("already in ERPNext"), "grey",
				"tally-sync-log?status=Skipped")}
		</div>`;

		const byType = this.table([
			{ label: __("Tally voucher type"), get: (r) => this.esc(r.vtype) },
			{ label: __("Count"), num: 1, get: (r) => r.count },
			{ label: __("Amount"), num: 1, get: (r) => this.money(r.amount) },
		], v.by_type, __("No Tally vouchers in this period"));

		const topTable = (rows, dt) => this.table([
			{ label: dt === "Customer" ? __("Customer") : __("Supplier"),
				get: (r) => this.link(frappe.router.slug(dt) + "/" + encodeURIComponent(r.party), r.display) },
			{ label: __("Balance"), num: 1, get: (r) => this.money(r.bal) },
		], rows, __("No balances"));

		const cbTable = this.table([
			{ label: __("Account"), get: (r) => this.link("account/" + encodeURIComponent(r.account), r.account_name) },
			{ label: __("Type"), get: (r) => this.esc(r.account_type) },
			{ label: __("Balance"), num: 1, get: (r) => this.money(r.bal) },
		], cb, __("No bank or cash accounts"));

		const masters = `<div class="td-masters">
			${this.tile(__("Accounts"), m.accounts || 0, __("Tally ledgers"), "", 'account?tally_ledger_name=["is","set"]')}
			${this.tile(__("Customers"), m.customers || 0, __("Sundry Debtors"), "", 'customer?tally_ledger_name=["is","set"]')}
			${this.tile(__("Suppliers"), m.suppliers || 0, __("Sundry Creditors"), "", 'supplier?tally_ledger_name=["is","set"]')}
			${this.tile(__("Items"), m.items || 0, __("Stock items"), "", 'item?tally_ledger_name=["is","set"]')}
		</div>`;

		const recent = this.table([
			{ label: __("Date"), get: (r) => frappe.datetime.str_to_user(r.posting_date) },
			{ label: __("Tally voucher"), get: (r) => this.esc(r.tally_voucher) },
			{ label: __("Party"), get: (r) => r.party
				? this.link(frappe.router.slug(r.party_type) + "/" + encodeURIComponent(r.party), r.party) : "" },
			{ label: __("Amount"), num: 1, get: (r) => this.money(r.amount) },
			{ label: __("ERPNext entry"), get: (r) => this.link("journal-entry/" + encodeURIComponent(r.name), r.name) },
		], v.recent, __("No Tally vouchers in this period"));

		const problems = this.table([
			{ label: __("Record"), get: (r) => this.link("tally-sync-log/" + r.name, r.tally_name || r.name) },
			{ label: __("Type"), get: (r) => this.esc(r.record_type) },
			{ label: __("Problem"), get: (r) => `<span class="td-msg">${this.esc(r.message)}</span>` },
		], failed, __("No failures"));

		const dupes = this.table([
			{ label: __("Tally voucher"), get: (r) => this.link("tally-sync-log/" + r.name, r.tally_name) },
			{ label: __("Matched ERPNext record"), get: (r) => r.reference_name
				? this.link(frappe.router.slug(r.reference_doctype) + "/" + encodeURIComponent(r.reference_name), r.reference_name) : "" },
			{ label: __("Amount"), num: 1, get: (r) => this.money(r.amount) },
		], skipped, __("No duplicates found"));

		this.$body.html(`
			${health}
			${tiles}
			<div class="td-grid">
				${this.card(__("Tally vouchers by month (amount)"), `<div class="td-chart"></div>`)}
				${this.card(__("By Tally voucher type"), byType)}
			</div>
			<div class="td-grid">
				${this.card(__("Top receivables"), topTable(rec.top, "Customer"),
					this.link("query-report/Accounts Receivable", __("Full report")))}
				${this.card(__("Top payables"), topTable(pay.top, "Supplier"),
					this.link("query-report/Accounts Payable", __("Full report")))}
			</div>
			<div class="td-grid">
				${this.card(__("Bank and cash balances"), cbTable)}
				${this.card(__("Masters from Tally"), masters +
					(d.draft_jes ? `<div class="td-note">${__("{0} imported Journal Entries are still in Draft.", [d.draft_jes])}
						${this.link('journal-entry?docstatus=0&tally_voucher=["is","set"]', __("Review"))}</div>` : ""))}
			</div>
			${this.card(__("Latest Tally vouchers"), recent, this.link('journal-entry?tally_voucher=["is","set"]', __("All")))}
			<div class="td-grid">
				${this.card(__("Needs attention"), problems, this.link("tally-sync-log?status=Failed", __("All failures")))}
				${this.card(__("Skipped as already in ERPNext"), dupes, this.link("tally-sync-log?status=Skipped", __("All")))}
			</div>`);

		const months = v.by_month || [];
		const el = this.$body.find(".td-chart")[0];
		if (el && months.length) {
			new frappe.Chart(el, {
				type: "bar", height: 240, colors: ["#2490EF"],
				data: { labels: months.map((x) => x.label), datasets: [{ name: __("Amount"), values: months.map((x) => x.amount) }] },
				tooltipOptions: { formatTooltipY: (y) => this.money(y) },
				axisOptions: { xIsSeries: 1 },
			});
		}
	}

	inject_css() {
		if (document.getElementById("tally-dash-css")) return;
		$(`<style id="tally-dash-css">
			.tally-dash { padding: 4px 0 40px; }
			.td-health { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin:4px 0 16px; }
			.td-error { flex-basis:100%; color: var(--red-600); font-size: 12px; }
			.td-tiles { display:grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap:12px; margin-bottom:16px; }
			.td-masters { display:grid; grid-template-columns: repeat(2, 1fr); gap:10px; }
			.td-tile-link, .td-tile-link:hover { text-decoration:none; color:inherit; }
			.td-tile { border:1px solid var(--border-color); border-radius:10px; padding:12px 14px; background: var(--card-bg); height:100%; }
			.td-tile-link .td-tile:hover { border-color: var(--primary); }
			.td-label { font-size:12px; color: var(--text-muted); }
			.td-value { font-size:22px; font-weight:600; margin-top:2px; }
			.td-sub { font-size:12px; color: var(--text-muted); }
			.td-tile.blue .td-value { color: var(--blue-600); } .td-tile.green .td-value { color: var(--green-600); }
			.td-tile.orange .td-value { color: var(--orange-600); } .td-tile.purple .td-value { color: var(--purple-600); }
			.td-tile.red .td-value { color: var(--red-600); }
			.td-grid { display:grid; grid-template-columns: 1fr 1fr; gap:12px; margin-bottom:12px; }
			@media (max-width: 900px) { .td-grid { grid-template-columns: 1fr; } }
			.td-card { border:1px solid var(--border-color); border-radius:10px; padding:12px 14px; background: var(--card-bg); margin-bottom:12px; overflow:auto; }
			.td-card-head { display:flex; justify-content:space-between; font-weight:600; margin-bottom:8px; }
			.td-card-head a { font-weight:400; font-size:12px; }
			.td-table { width:100%; font-size:13px; }
			.td-table th { color: var(--text-muted); font-weight:500; border-bottom:1px solid var(--border-color); padding:6px 4px; }
			.td-table td { border-bottom:1px solid var(--border-color); padding:6px 4px; vertical-align:top; }
			.td-table .num { text-align:right; white-space:nowrap; }
			.td-msg { font-size:12px; color: var(--text-muted); }
			.td-empty { color: var(--text-muted); font-size:13px; padding:8px 0; }
			.td-note { margin-top:10px; font-size:12px; color: var(--orange-600); }
		</style>`).appendTo("head");
	}
}
