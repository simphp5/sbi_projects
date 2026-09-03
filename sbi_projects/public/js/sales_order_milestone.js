// Copyright (c) 2026, Velmaska and contributors
// Milestone billing: Sales Order -> Create -> Milestone Invoice
// Select one or more payment-schedule stages, choose combined vs separate
// invoices, and open the (first) draft Sales Invoice in a new tab.

frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;
		if (frm.doc.status === "Closed") return;
		if (!(frm.doc.payment_schedule || []).length) return;

		frm.add_custom_button(
			__("Milestone Invoice"),
			() => sbi_open_milestone_dialog(frm),
			__("Create")
		);
	},
});

function sbi_open_milestone_dialog(frm) {
	frappe.call({
		method: "sbi_projects.api.milestone_billing.get_payment_terms",
		args: { sales_order: frm.doc.name },
		freeze: true,
		callback(r) {
			const data = r.message || {};
			const all_rows = data.rows || [];
			const open_rows = all_rows.filter((d) => !d.billed);
			const done_rows = all_rows.filter((d) => d.billed);

			if (!open_rows.length) {
				frappe.msgprint({
					title: __("Nothing to bill"),
					message: __("All stages on this Sales Order are already invoiced."),
					indicator: "green",
				});
				return;
			}
			sbi_show_milestone_dialog(frm, open_rows, done_rows, data.project);
		},
	});
}

function sbi_show_milestone_dialog(frm, open_rows, done_rows, project) {
	const terms_data = open_rows.map((r) => Object.assign({ select: 0 }, r));
	const fields = [];

	if (!project) {
		fields.push({
			fieldtype: "HTML",
			options:
				`<div class="alert alert-warning" style="margin-bottom:12px;">` +
				__("No Project is linked to this Sales Order, so the invoice will post to the company default cost center. Create the Project first for site-wise costing.") +
				`</div>`,
		});
	}

	if (done_rows.length) {
		fields.push({
			fieldtype: "HTML",
			options: sbi_billed_html(done_rows),
		});
	}

	fields.push(
		{
			fieldname: "terms",
			fieldtype: "Table",
			label: __("Stages to Bill"),
			cannot_add_rows: true,
			cannot_delete_rows: true,
			in_place_edit: false,
			data: terms_data,
			get_data: () => terms_data,
			fields: [
				{ fieldname: "select", label: __("Bill"), fieldtype: "Check", in_list_view: 1, columns: 1 },
				{ fieldname: "stage", label: __("Stage"), fieldtype: "Data", in_list_view: 1, read_only: 1, columns: 3 },
				{ fieldname: "payment_term", label: __("Payment Term"), fieldtype: "Data", in_list_view: 1, read_only: 1, columns: 3 },
				{ fieldname: "invoice_portion", label: __("%"), fieldtype: "Percent", in_list_view: 1, read_only: 1, columns: 1 },
				{ fieldname: "payment_amount", label: __("Amount"), fieldtype: "Currency", in_list_view: 1, read_only: 1, columns: 3 },
				{ fieldname: "row_name", fieldtype: "Data", hidden: 1 },
				{ fieldname: "due_date", fieldtype: "Date", hidden: 1 },
				{ fieldname: "description", fieldtype: "Small Text", hidden: 1 },
			],
		},
		{ fieldtype: "Section Break" },
		{
			fieldname: "split",
			label: __("When multiple stages are selected"),
			fieldtype: "Select",
			options: ["Single combined invoice", "Separate invoice per stage"].join("\n"),
			default: "Single combined invoice",
			description: __("Ignored when only one stage is selected."),
		},
		{ fieldname: "cb1", fieldtype: "Column Break" },
		{
			fieldname: "billing_mode",
			label: __("Billing Mode"),
			fieldtype: "Select",
			options: ["Rate Scaled", "Single Service Item", "Proportional Qty"].join("\n"),
			default: "Rate Scaled",
			reqd: 1,
			description: __("Rate Scaled keeps SO items and scales each rate to the stage %."),
		},
		{
			fieldname: "service_item",
			label: __("Service Item"),
			fieldtype: "Link",
			options: "Item",
			depends_on: "eval:doc.billing_mode=='Single Service Item'",
			mandatory_depends_on: "eval:doc.billing_mode=='Single Service Item'",
			get_query: () => ({ filters: { is_stock_item: 0, disabled: 0 } }),
		}
	);

	const d = new frappe.ui.Dialog({
		title: __("Create Milestone Invoice"),
		size: "extra-large",
		fields: fields,
		primary_action_label: __("Create Sales Invoice"),
		primary_action() {
			const grid_data = d.fields_dict.terms.grid.get_data() || [];
			const selected = grid_data.filter((row) => row.select);
			if (!selected.length) {
				frappe.msgprint(__("Tick at least one stage"));
				return;
			}
			const values = d.get_values(true) || {};
			if (values.billing_mode === "Single Service Item" && !values.service_item) {
				frappe.msgprint(__("Select a Service Item"));
				return;
			}
			const split = values.split === "Separate invoice per stage" ? "separate" : "combined";

			frappe.call({
				method: "sbi_projects.api.milestone_billing.make_milestone_invoice",
				args: {
					sales_order: frm.doc.name,
					selected_rows: selected.map((row) => row.row_name),
					billing_mode: values.billing_mode,
					service_item: values.service_item || null,
					split: split,
				},
				freeze: true,
				freeze_message: __("Creating milestone invoice..."),
				callback(r) {
					if (!r.message || !r.message.invoice) return;
					d.hide();
					const doclist = frappe.model.sync(r.message.invoice);
					const first = doclist[0];
					const others = r.message.others || [];

					// open the (first) invoice in a new tab
					window.open(
						`/app/sales-invoice/${encodeURIComponent(first.name)}`,
						"_blank",
						"noopener"
					);

					if (others.length) {
						frappe.msgprint({
							title: __("Invoices created"),
							message:
								__("Created {0} draft invoices. Opened the first in a new tab.", [others.length + 1]) +
								"<br>" +
								[first.name].concat(others).map((n) => "&bull; " + frappe.utils.escape_html(n)).join("<br>"),
							indicator: "green",
						});
					}
					frm.reload_doc();
				},
			});
		},
	});

	d.fields_dict.terms.grid.wrapper.on("change", "input[data-fieldname='select']", () => {
		setTimeout(() => sbi_update_total(d), 100);
	});

	d.show();
}

function sbi_update_total(d) {
	const rows = d.fields_dict.terms.grid.get_data() || [];
	const picked = rows.filter((r) => r.select);
	const pct = picked.reduce((a, r) => a + flt(r.invoice_portion), 0);
	const amt = picked.reduce((a, r) => a + flt(r.payment_amount), 0);
	d.set_title(
		picked.length
			? __("Create Milestone Invoice - {0}% / {1}", [format_number(pct, null, 2), format_currency(amt)])
			: __("Create Milestone Invoice")
	);
}

function sbi_billed_html(done_rows) {
	const items = done_rows
		.map((r) => {
			const st = r.status ? ` <span class="text-muted">(${frappe.utils.escape_html(r.status)})</span>` : "";
			const inv = r.sales_invoice
				? `<a href="/app/sales-invoice/${encodeURIComponent(r.sales_invoice)}" target="_blank" rel="noopener">${frappe.utils.escape_html(r.sales_invoice)}</a>`
				: "";
			return `<li>${frappe.utils.escape_html(r.stage || r.payment_term || "")} - ${format_number(flt(r.invoice_portion), null, 2)}% - ${inv}${st}</li>`;
		})
		.join("");
	return `<div class="alert alert-info" style="margin-bottom:12px;"><b>${__("Already billed")}</b><ul style="margin:6px 0 0 16px;padding:0;">${items}</ul></div>`;
}
