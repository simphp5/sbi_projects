// Copyright (c) 2026, Velmaska and contributors
// Cash Flow - owner dashboard. Data: sbi_projects.cashflow.engine.get_dashboard
frappe.pages["cash-flow"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Cash Flow"), single_column: true });
	const dash = (wrapper.cash_flow = new CashFlowDashboard(page));
	frappe.db.get_single_value("Cash Flow Settings", "default_period")
		.then((v) => {
			if (v && v !== dash.period.get_value()) dash.period.set_value(v); // change event refreshes
			else dash.refresh();
		})
		.catch(() => dash.refresh());
};

frappe.pages["cash-flow"].on_page_show = function (wrapper) {
	if (wrapper.cash_flow && wrapper.cash_flow.data) wrapper.cash_flow.refresh();
};

const CF_ALL = "__all__";
const CF_ALL_LABEL = __("All companies");
const CF_PERIODS = ["Today", "This Week", "This Month", "This Quarter", "This Half Year", "This Financial Year",
	"Last Month", "Last Quarter", "Last Financial Year", "Custom"];
// validated categorical order (fixed, never cycled): one colour per expense category
const CF_SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];
const CF_REPORTS = [
	["Cash Flow Summary", __("Money in / out and cash balance by period")],
	["Expense Split", __("Expenses by category and period")],
	["Profit and Loss by Period", __("Sales, costs and profit per period")],
	["Project Profitability", __("Each project: sales, costs, profit, budget")],
	["Budget vs Actual BOQ", __("Project BOQ budget against actual cost")],
	["Site Cash Position", __("Cash given to sites vs spent")],
];
const CF_STD_REPORTS = [
	["Accounts Receivable", __("Who owes us")],
	["Accounts Payable", __("Whom we owe")],
	["Profit and Loss Statement", __("Standard P&L")],
	["Balance Sheet", __("Standard balance sheet")],
	["General Ledger", __("Every entry")],
];

class CashFlowDashboard {
	constructor(page) {
		this.page = page;
		const re = () => this.refresh();
		this.company = page.add_field({ fieldname: "company", label: __("Company"), fieldtype: "Select",
			options: CF_ALL_LABEL, default: CF_ALL_LABEL, change: () => !this._filling && this.refresh(true) });
		this.project = page.add_field({ fieldname: "project", label: __("Project (all if empty)"), fieldtype: "Link",
			options: "Project", change: re,
			get_query: () => {
				const c = this.company_value();
				return c && c !== CF_ALL ? { filters: { company: c } } : {};
			} });
		this.period = page.add_field({ fieldname: "period", label: __("Period"), fieldtype: "Select",
			options: CF_PERIODS.map((p) => ({ value: p, label: __(p) })), default: "This Financial Year",
			change: () => { this.toggle_dates(); if (this.period.get_value() !== "Custom") this.refresh(); } });
		this.from = page.add_field({ fieldname: "from_date", label: __("From"), fieldtype: "Date",
			change: () => this.period.get_value() === "Custom" && this.refresh() });
		this.to = page.add_field({ fieldname: "to_date", label: __("To"), fieldtype: "Date",
			change: () => this.period.get_value() === "Custom" && this.refresh() });
		this.gran = page.add_field({ fieldname: "granularity", label: __("Charts by"), fieldtype: "Select",
			options: ["Auto", "Daily", "Weekly", "Monthly", "Quarterly"].map((g) => ({ value: g, label: __(g) })),
			default: "Auto", change: re });
		page.set_primary_action(__("Refresh"), re, "refresh");
		CF_REPORTS.concat(CF_STD_REPORTS).forEach(([name]) =>
			page.add_inner_button(__(name), () => this.open_report(name), __("Reports")));
		page.add_inner_button(__("Cash Flow Settings"), () => frappe.set_route("Form", "Cash Flow Settings"));
		this.$body = $(`<div class="cf-dash"></div>`).appendTo(page.main);
		this.inject_css();
		this.toggle_dates();
	}

	company_value() {
		const v = this.company.get_value();
		return !v || v === CF_ALL_LABEL ? CF_ALL : v;
	}

	toggle_dates() {
		const custom = this.period.get_value() === "Custom";
		this.from.$wrapper.toggle(custom);
		this.to.$wrapper.toggle(custom);
	}

	args() {
		return {
			company: this.company_value(), project: this.project.get_value() || null,
			period: this.period.get_value(), from_date: this.from.get_value(), to_date: this.to.get_value(),
			granularity: this.gran.get_value(),
		};
	}

	refresh(company_changed) {
		if (company_changed && this.project.get_value()) {
			this.project.set_value("");
			return; // the project change triggers the refresh
		}
		this.$body.html(`<div class="text-muted" style="padding:40px;text-align:center">${__("Loading...")}</div>`);
		frappe.call({ method: "sbi_projects.cashflow.engine.get_dashboard", args: this.args() }).then((r) => {
			const d = r.message || {};
			this.data = d;
			this.fill_companies(d);
			this.render(d);
		});
	}

	fill_companies(d) {
		const list = [CF_ALL_LABEL].concat(d.companies || []);
		if (this.company.df.options === list.join("\n")) return;
		this._filling = true;
		const cur = this.company.get_value() || CF_ALL_LABEL;
		this.company.df.options = list.join("\n");
		this.company.refresh();
		this.company.set_value(list.includes(cur) ? cur : CF_ALL_LABEL).then(() => (this._filling = false));
	}

	open_report(name) {
		const a = this.args();
		const opts = {};
		if (a.company !== CF_ALL) opts.company = a.company;
		if (CF_REPORTS.some((r) => r[0] === name)) {
			Object.assign(opts, { period: a.period, from_date: this.data?.from_date, to_date: this.data?.to_date });
			if (a.project) opts.project = a.project;
		} else if (this.data) {
			Object.assign(opts, { from_date: this.data.from_date, to_date: this.data.to_date,
				report_date: this.data.to_date });
		}
		window.open(`/app/query-report/${encodeURIComponent(name)}?` + $.param(opts), "_blank");
	}

	// ------------------------------------------------------------ helpers
	money(v) {
		return format_currency(v || 0, frappe.defaults.get_default("currency") || "INR", 0);
	}
	short(v) {
		const a = Math.abs(v || 0), s = v < 0 ? "-" : "";
		if (a >= 1e7) return s + "₹" + (a / 1e7).toFixed(2) + " Cr";
		if (a >= 1e5) return s + "₹" + (a / 1e5).toFixed(2) + " L";
		return this.money(v);
	}
	esc(v) {
		return frappe.utils.escape_html(v == null ? "" : String(v));
	}
	link(route, text) {
		return `<a href="/app/${route}" target="_blank" rel="noopener">${this.esc(text)}</a>`;
	}
	tile(label, value, sub, tone, route) {
		const inner = `<div class="cf-tile ${tone || ""}"><div class="cf-label">${label}</div>
			<div class="cf-value">${value}</div>${sub ? `<div class="cf-sub">${sub}</div>` : ""}</div>`;
		return route ? `<a class="cf-tile-link" href="/app/${route}" target="_blank" rel="noopener">${inner}</a>` : inner;
	}
	card(title, body, id, note) {
		return `<div class="cf-card"><div class="cf-card-head"><span>${title}</span>${note ? `<span class="cf-note">${note}</span>` : ""}</div>
			${id ? `<div id="${id}"></div>` : ""}${body || ""}</div>`;
	}
	pct_bar(p) {
		if (p == null) return `<span class="text-muted">-</span>`;
		const tone = p > 100 ? "over" : p > 85 ? "near" : "ok";
		return `<div class="cf-bar"><div class="cf-bar-fill ${tone}" style="width:${Math.min(p, 100)}%"></div></div>
			<span class="cf-bar-text ${tone}">${p}%</span>`;
	}

	// ------------------------------------------------------------ render
	render(d) {
		const k = d.kpi || {};
		const profit_tone = k.profit >= 0 ? "good" : "bad";
		const scope = d.project ? __("Project {0}", [this.esc(d.project)]) : this.esc(d.company === CF_ALL ? CF_ALL_LABEL : d.company);
		const drafts = (k.draft_sales || k.draft_purchases)
			? `<div class="cf-alert">${__("Not yet counted: {0} draft sales invoices ({1}) and {2} draft purchase invoices ({3}). Submit them to include them.",
				[k.draft_sales, this.short(k.draft_sales_amount), k.draft_purchases, this.short(k.draft_purchases_amount)])}
				${this.link('sales-invoice?docstatus=0', __("Open draft sales"))} · ${this.link('purchase-invoice?docstatus=0', __("Open draft purchases"))}</div>` : "";

		const head = `<div class="cf-head">
			<div><b>${scope}</b> · ${frappe.datetime.str_to_user(d.from_date)} – ${frappe.datetime.str_to_user(d.to_date)}
			<span class="text-muted">· ${__("charts by")} ${__(d.granularity)} · ${__("source")}: ${this.esc(d.source)}</span></div></div>`;

		const tiles = `<div class="cf-tiles">
			${this.tile(__("Sales value"), this.short(k.sales), __("income booked in period"), "blue",
				d.project ? `sales-invoice?project=${encodeURIComponent(d.project)}` : "query-report/Profit and Loss by Period")}
			${this.tile(__("Expenses"), this.short(k.expenses), __("all 7 categories"), "orange", "query-report/Expense Split")}
			${this.tile(k.profit >= 0 ? __("Profit") : __("Loss"), this.short(Math.abs(k.profit)),
				k.margin == null ? "" : __("margin {0}%", [k.margin]), profit_tone)}
			${this.tile(__("Cash + bank now"), this.short(k.closing_cash), __("opening {0}", [this.short(k.opening_cash)]), "plain",
				"query-report/Cash Flow Summary")}
			${this.tile(__("Money in"), this.short(k.cash_in), __("receipts in period"), "plain")}
			${this.tile(__("Money out"), this.short(k.cash_out), __("payments in period"), "plain")}
			${this.tile(__("To receive"), this.short(k.receivable), k.receivable_overdue ? __("{0} overdue", [this.short(k.receivable_overdue)]) : __("nothing overdue"),
				k.receivable_overdue ? "warn" : "plain", "query-report/Accounts Receivable")}
			${this.tile(__("To pay"), this.short(k.payable), k.payable_overdue ? __("{0} overdue", [this.short(k.payable_overdue)]) : __("nothing overdue"),
				k.payable_overdue ? "warn" : "plain", "query-report/Accounts Payable")}
		</div>`;

		const split = d.expense_split || {};
		const total_exp = Object.values(split).reduce((a, b) => a + b, 0);
		const cats = d.categories || [];
		const split_table = `<table class="cf-table"><thead><tr><th>${__("Category")}</th><th class="r">${__("Amount")}</th><th class="r">%</th></tr></thead><tbody>
			${cats.map((c, i) => `<tr><td><span class="cf-key" style="background:${CF_SERIES[i]}"></span>${__(c)}</td>
				<td class="r">${this.money(split[c])}</td><td class="r">${total_exp ? (split[c] / total_exp * 100).toFixed(1) : "0.0"}</td></tr>`).join("")}
			</tbody><tfoot><tr><th>${__("Total")}</th><th class="r">${this.money(total_exp)}</th><th class="r">100</th></tr></tfoot></table>`;

		const budget = this.budget_html(d.budget || {});
		const cash = d.cash || {};
		const flow_list = (obj) => Object.entries(obj || {}).map(([k2, v]) =>
			`<div class="cf-row"><span>${__(k2)}</span><b>${this.money(v)}</b></div>`).join("");
		const balances = (cash.balances || []).map((b) => `<div class="cf-row"><span>${this.link(
			"query-report/General Ledger?account=" + encodeURIComponent(b.account), b.account)} <span class="text-muted small">${__(b.account_type)}</span></span>
			<b class="${b.balance < 0 ? "neg" : ""}">${this.money(b.balance)}</b></div>`).join("") || `<div class="text-muted">${__("No cash or bank ledgers")}</div>`;

		const party_table = (rows, doctype, field) => rows && rows.length ? `<table class="cf-table"><thead><tr><th>${__("Party")}</th>
			<th class="r">${__("Outstanding")}</th><th class="r">${__("Overdue")}</th></tr></thead><tbody>
			${rows.map((r) => `<tr><td>${this.link(`${doctype}?${field}=${encodeURIComponent(r.party)}&docstatus=1&outstanding_amount=["!=",0]`, r.party)}</td>
				<td class="r">${this.money(r.amount)}</td><td class="r ${r.overdue ? "neg" : ""}">${this.money(r.overdue)}</td></tr>`).join("")}</tbody></table>`
			: `<div class="text-muted">${__("Nothing outstanding")}</div>`;

		const site = (d.site_cash || []).length ? `<table class="cf-table"><thead><tr><th>${__("Project")}</th><th class="r">${__("Given to site")}</th>
			<th class="r">${__("Spent")}</th><th class="r">${__("With site")}</th></tr></thead><tbody>
			${d.site_cash.slice(0, 12).map((r) => `<tr><td>${this.link("project/" + encodeURIComponent(r.project), r.project)}</td>
				<td class="r">${this.money(r.issued)}</td><td class="r">${this.money(r.spent)}</td>
				<td class="r ${r.balance < 0 ? "neg" : ""}">${this.money(r.balance)}</td></tr>`).join("")}</tbody></table>`
			: `<div class="text-muted">${__("No site cash issued yet")}</div>`;

		const reports = `<div class="cf-reports">${CF_REPORTS.concat(CF_STD_REPORTS).map(([n, t]) =>
			`<a class="cf-report" data-report="${this.esc(n)}"><b>${__(n)}</b><span>${t}</span></a>`).join("")}</div>`;

		this.$body.html(`${head}${drafts}${tiles}
			<div class="cf-grid">
				${this.card(__("Sales vs expenses"), "", "cf-sales")}
				${this.card(__("Profit / loss by period"), "", "cf-profit")}
			</div>
			<div class="cf-grid">
				${this.card(__("Expense split"), `<div class="cf-split"><div id="cf-donut"></div>${split_table}</div>`)}
				${this.card(__("Expenses by period"), "", "cf-exp-period")}
			</div>
			${this.card(__("Budget vs actual"), budget.html, budget.chart ? "cf-budget" : "", budget.note)}
			<div class="cf-grid">
				${this.card(__("Money in vs money out"), "", "cf-cash")}
				${this.card(__("Cash + bank balance"), "", "cf-closing")}
			</div>
			<div class="cf-grid three">
				${this.card(__("Where money came from"), flow_list(cash.in_split))}
				${this.card(__("Where money went"), flow_list(cash.out_split))}
				${this.card(__("Cash and bank accounts"), balances)}
			</div>
			<div class="cf-grid three">
				${this.card(__("Customers to collect from"), party_table(d.top_receivable, "sales-invoice", "customer"))}
				${this.card(__("Suppliers to pay"), party_table(d.top_payable, "purchase-invoice", "supplier"))}
				${this.card(__("Site cash"), site)}
			</div>
			${this.card(__("Reports"), reports)}`);
		this.$body.find(".cf-report").on("click", (e) => this.open_report($(e.currentTarget).attr("data-report")));
		this.draw(d, budget);
	}

	budget_html(b) {
		if (b.mode === "project") {
			const rows = b.rows || [];
			return {
				chart: true,
				note: __("BOQ budget for the whole job vs everything spent so far"),
				html: `<table class="cf-table"><thead><tr><th>${__("Category")}</th><th class="r">${__("Budget (BOQ)")}</th>
					<th class="r">${__("Actual")}</th><th class="r">${__("Left")}</th><th style="width:180px">${__("Used")}</th></tr></thead><tbody>
					${rows.map((r) => `<tr><td>${__(r.category)}</td><td class="r">${this.money(r.budget)}</td><td class="r">${this.money(r.actual)}</td>
						<td class="r ${r.variance < 0 ? "neg" : ""}">${this.money(r.variance)}</td><td>${this.pct_bar(r.used_pct)}</td></tr>`).join("")}
					</tbody><tfoot><tr><th>${__("Total")}</th><th class="r">${this.money(b.budget_total)}</th><th class="r">${this.money(b.actual_total)}</th>
					<th class="r">${this.money(b.budget_total - b.actual_total)}</th><th>${this.pct_bar(b.budget_total ? Math.round(b.actual_total / b.budget_total * 1000) / 10 : null)}</th></tr></tfoot></table>
					<div class="text-muted small">${__("Sales booked to this project so far: {0}", [this.money(b.sales_to_date)])}</div>`,
			};
		}
		const rows = b.rows || [];
		return {
			chart: false,
			note: __("Projects with a BOQ, most used first. Pick a project above for the category split."),
			html: rows.length ? `<table class="cf-table"><thead><tr><th>${__("Project")}</th><th>${__("Status")}</th><th class="r">${__("Budget (BOQ)")}</th>
				<th class="r">${__("Actual")}</th><th class="r">${__("Left")}</th><th style="width:180px">${__("Used")}</th><th class="r">${__("Sales")}</th></tr></thead><tbody>
				${rows.map((r) => `<tr><td><a class="cf-pick" data-project="${this.esc(r.project)}">${this.esc(r.label)}</a></td><td>${this.esc(__(r.status || ""))}</td>
					<td class="r">${this.money(r.budget)}</td><td class="r">${this.money(r.actual)}</td>
					<td class="r ${r.variance < 0 ? "neg" : ""}">${this.money(r.variance)}</td><td>${this.pct_bar(r.used_pct)}</td>
					<td class="r">${this.money(r.sales)}</td></tr>`).join("")}</tbody></table>
				${b.more ? `<div class="text-muted small">${__("{0} more in the Budget vs Actual BOQ report", [b.more])}</div>` : ""}`
				: `<div class="text-muted">${__("No project has a Project BOQ yet.")}</div>`,
		};
	}

	draw(d, budget) {
		const labels = d.labels || [];
		const fmt = (v) => this.short(v);
		const chart = (id, opts) => {
			const el = this.$body.find("#" + id).get(0);
			if (!el) return;
			try {
				new frappe.Chart(el, Object.assign({ height: 240, axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 1 },
					tooltipOptions: { formatTooltipY: fmt }, barOptions: { spaceRatio: 0.4 } }, opts));
			} catch (e) {
				console.warn("Cash Flow chart", id, e);
			}
		};
		if (!labels.length) return;
		chart("cf-sales", { type: "bar", colors: [CF_SERIES[0], CF_SERIES[1]],
			data: { labels, datasets: [{ name: __("Sales"), values: d.sales_series }, { name: __("Expenses"), values: d.expense_series }] } });
		chart("cf-profit", { type: "bar", colors: [CF_SERIES[2]],
			data: { labels, datasets: [{ name: __("Profit (below 0 = loss)"), values: d.profit_series }] } });
		const cats = d.categories || [];
		const split = d.expense_split || {};
		const pos = cats.map((c, i) => [c, split[c], CF_SERIES[i]]).filter((x) => x[1] > 0);
		if (pos.length) {
			chart("cf-donut", { type: "donut", height: 240, colors: pos.map((x) => x[2]),
				data: { labels: pos.map((x) => __(x[0])), datasets: [{ values: pos.map((x) => Math.round(x[1])) }] } });
		}
		chart("cf-exp-period", { type: "bar", colors: CF_SERIES.slice(0, cats.length), barOptions: { stacked: 1, spaceRatio: 0.4 },
			data: { labels, datasets: cats.map((c) => ({ name: __(c), values: (d.expense_by_period || {})[c] || [] })) } });
		const cash = d.cash || {};
		chart("cf-cash", { type: "bar", colors: [CF_SERIES[0], CF_SERIES[1]],
			data: { labels, datasets: [{ name: __("Money in"), values: cash.in || [] }, { name: __("Money out"), values: cash.out || [] }] } });
		chart("cf-closing", { type: "line", colors: [CF_SERIES[0]], lineOptions: { regionFill: 1, dotSize: 4 },
			data: { labels, datasets: [{ name: __("Cash + bank at period end"), values: cash.closing || [] }] } });
		if (budget.chart) {
			const rows = (d.budget || {}).rows || [];
			chart("cf-budget", { type: "bar", colors: [CF_SERIES[0], CF_SERIES[1]], axisOptions: { xIsSeries: 0, shortenYAxisNumbers: 1 },
				data: { labels: rows.map((r) => __(r.category.split(" (")[0])),
					datasets: [{ name: __("Budget"), values: rows.map((r) => r.budget) }, { name: __("Actual"), values: rows.map((r) => r.actual) }] } });
		}
		this.$body.find(".cf-pick").on("click", (e) => this.project.set_value($(e.currentTarget).attr("data-project")));
	}

	inject_css() {
		if (document.getElementById("cf-css")) return;
		$(`<style id="cf-css">
			.cf-dash { padding: 4px 0 40px; }
			.cf-head { margin: 4px 0 12px; font-size: 13px; }
			.cf-alert { background: var(--yellow-50, #fff8e6); border: 1px solid var(--yellow-200, #f5d98b); border-radius: 8px;
				padding: 8px 12px; margin-bottom: 12px; font-size: 13px; }
			.cf-tiles { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
			.cf-tile-link, .cf-tile-link:hover { text-decoration: none; color: inherit; }
			.cf-tile { border: 1px solid var(--border-color); border-radius: 10px; padding: 12px 14px; background: var(--card-bg); height: 100%; }
			.cf-tile-link .cf-tile:hover { border-color: var(--gray-500); }
			.cf-label { font-size: 12px; color: var(--text-muted); }
			.cf-value { font-size: 22px; font-weight: 600; margin-top: 2px; color: var(--text-color); }
			.cf-sub { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
			.cf-tile.good { border-left: 4px solid #0ca30c; } .cf-tile.bad { border-left: 4px solid #d03b3b; }
			.cf-tile.blue { border-left: 4px solid #2a78d6; } .cf-tile.orange { border-left: 4px solid #eb6834; }
			.cf-tile.warn { border-left: 4px solid #fab219; }
			.cf-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
			.cf-grid.three { grid-template-columns: 1fr 1fr 1fr; }
			.cf-card { border: 1px solid var(--border-color); border-radius: 10px; padding: 12px 14px; margin-bottom: 16px;
				background: var(--card-bg); min-width: 0; }
			.cf-card-head { display: flex; justify-content: space-between; gap: 8px; font-weight: 600; margin-bottom: 8px; flex-wrap: wrap; }
			.cf-note { font-weight: 400; font-size: 12px; color: var(--text-muted); }
			.cf-split { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; align-items: center; }
			.cf-table { width: 100%; font-size: 13px; border-collapse: collapse; }
			.cf-table th { font-weight: 600; color: var(--text-muted); font-size: 12px; border-bottom: 1px solid var(--border-color); padding: 6px 4px; }
			.cf-table td { border-bottom: 1px solid var(--border-color); padding: 6px 4px; }
			.cf-table tfoot th { color: var(--text-color); border-bottom: 0; }
			.cf-table .r { text-align: right; white-space: nowrap; }
			.cf-key { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 6px; vertical-align: -1px; }
			.cf-row { display: flex; justify-content: space-between; gap: 8px; padding: 6px 0; border-bottom: 1px solid var(--border-color); font-size: 13px; }
			.cf-row:last-child { border-bottom: 0; }
			.neg { color: #d03b3b; }
			.cf-bar { display: inline-block; width: 110px; height: 8px; background: var(--gray-200, #e1e0d9); border-radius: 4px; vertical-align: middle; overflow: hidden; }
			.cf-bar-fill { height: 100%; border-radius: 4px; } .cf-bar-fill.ok { background: #0ca30c; }
			.cf-bar-fill.near { background: #fab219; } .cf-bar-fill.over { background: #d03b3b; }
			.cf-bar-text { margin-left: 6px; font-size: 12px; } .cf-bar-text.over { color: #d03b3b; font-weight: 600; }
			.cf-pick { cursor: pointer; }
			.cf-reports { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; }
			.cf-report { display: block; border: 1px solid var(--border-color); border-radius: 8px; padding: 10px 12px; cursor: pointer; color: inherit; }
			.cf-report:hover { border-color: var(--gray-500); text-decoration: none; }
			.cf-report span { display: block; font-size: 12px; color: var(--text-muted); }
			@media (max-width: 991px) { .cf-tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); }
				.cf-grid, .cf-grid.three, .cf-split { grid-template-columns: 1fr; } }
		</style>`).appendTo(document.head);
	}
}
