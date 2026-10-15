// Copyright (c) 2026, Velmaska and contributors
frappe.ui.form.on("Cash Flow Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Open Cash Flow Dashboard"), () => frappe.set_route("cash-flow"));
		frm.add_custom_button(__("Check Expense Ledgers"), () => {
			frappe.call({ method: "sbi_projects.sbi_projects.doctype.cash_flow_settings.cash_flow_settings.check_expense_ledgers" })
				.then((r) => {
					const rows = r.message || [];
					const esc = frappe.utils.escape_html;
					const html = rows.length ? `<table class="table table-sm table-bordered"><thead><tr><th>${__("Category")}</th><th>${__("Expense ledger")}</th></tr></thead><tbody>`
						+ rows.map((x) => `<tr><td>${esc(x.category)}</td><td>${esc(x.account)}</td></tr>`).join("") + "</tbody></table>"
						: __("No expense ledgers found.");
					frappe.msgprint({ title: __("Where each expense ledger goes"), message: html, wide: true });
				});
		});
	},
});
