// Copyright (c) 2026, Velmaska and contributors
// Milestone billing: Sales Order -> Create -> Milestone Invoice

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
			const all_rows = r.message || [];
			const open_rows = all_rows.filter((d) => !d.billed);
			const done_rows = all_rows.filter((d) => d.billed);

			if (!open_rows.length) {
				frappe.msgprint({
					title: __("Nothing to bill"),
					message: __("All Payment Terms on this Sales Order are already invoiced."),
					indicator: "green",
				});
				return;
			}

			sbi_show_milestone_dialog(frm, open_rows, done_rows);
		},
	});
}

function sbi_show_milestone_dialog(frm, open_rows, done_rows) {
	const terms_data = open_rows.map((r) => Object.assign({ select: 0 }, r));

	const fields = [];

	if (done_rows.length) {
		fields.push({
			fieldtype: "HTML",
			fieldname: "already_billed",
			options: sbi_billed_html(done_rows),
		});
	}

	fields.push(
		{
			fieldname: "terms",
			fieldtype: "Table",
			label: __("Payment Terms to Bill"),
			cannot_add_rows: true,
			cannot_delete_rows: true,
			in_place_edit: false,
			data: terms_data,
			get_data: () => terms_data,
			fields: [
				{
					fieldname: "select",
					label: __("Bill"),
					fieldtype: "Check",
					in_list_view: 1,
					columns: 1,
				},
				{
					fieldname: "payment_term",
					label: __("Payment Term"),
					fieldtype: "Data",
					in_list_view: 1,
					read_only: 1,
					columns: 3,
				},
				{
					fieldname: "due_date",
					label: __("Due Date"),
					fieldtype: "Date",
					in_list_view: 1,
					read_only: 1,
					columns: 2,
				},
				{
					fieldname: "invoice_portion",
					label: __("%"),
					fieldtype: "Percent",
					in_list_view: 1,
					read_only: 1,
					columns: 2,
				},
				{
					fieldname: "payment_amount",
					label: __("Amount"),
					fieldtype: "Currency",
					in_list_view: 1,
					read_only: 1,
					columns: 3,
				},
				{ fieldname: "row_name", fieldtype: "Data", hidden: 1 },
				{ fieldname: "description", fieldtype: "Small Text", hidden: 1 },
			],
		},
		{ fieldtype: "Section Break" },
		{
			fieldname: "billing_mode",
			label: __("Billing Mode"),
			fieldtype: "Select",
			options: ["Proportional Qty", "Single Service Item"].join("\n"),
			default: "Proportional Qty",
			reqd: 1,
			description: __(
				"Proportional Qty keeps item-wise HSN and updates SO % Billed. Single Service Item is for advance / erection milestones."
			),
		},
		{
			fieldname: "service_item",
			label: __("Milestone Service Item"),
			fieldtype: "Link",
			options: "Item",
			depends_on: "eval:doc.billing_mode=='Single Service Item'",
			mandatory_depends_on: "eval:doc.billing_mode=='Single Service Item'",
			get_query: () => ({ filters: { is_stock_item: 0, disabled: 0 } }),
		}
	);

	const d = new frappe.ui.Dialog({
		title: __("Create Milestone Invoice"),
		size: "large",
		fields: fields,
		primary_action_label: __("Create Invoice"),
		primary_action() {
			const grid_data = d.fields_dict.terms.grid.get_data() || [];
			const selected = grid_data.filter((row) => row.select);

			if (!selected.length) {
				frappe.msgprint(__("Tick at least one Payment Term"));
				return;
			}

			const values = d.get_values(true) || {};

			if (values.billing_mode === "Single Service Item" && !values.service_item) {
				frappe.msgprint(__("Select a Milestone Service Item"));
				return;
			}

			frappe.call({
				method: "sbi_projects.api.milestone_billing.make_milestone_invoice",
				args: {
					sales_order: frm.doc.name,
					selected_rows: selected.map((row) => row.row_name),
					billing_mode: values.billing_mode,
					service_item: values.service_item || null,
				},
				freeze: true,
				freeze_message: __("Creating Milestone Invoice..."),
				callback(r) {
					if (!r.message) return;
					d.hide();
					const doclist = frappe.model.sync(r.message);
					frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
				},
			});
		},
	});

	// live total of the ticked portions
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
			? __("Create Milestone Invoice — {0}% / {1}", [
					format_number(pct, null, 2),
					format_currency(amt),
			  ])
			: __("Create Milestone Invoice")
	);
}

function sbi_billed_html(done_rows) {
	const items = done_rows
		.map(
			(r) =>
				`<li>${frappe.utils.escape_html(r.payment_term || "")} —
				 ${format_number(flt(r.invoice_portion), null, 2)}% —
				 <a href="/app/sales-invoice/${encodeURIComponent(r.sales_invoice || "")}">
				 ${frappe.utils.escape_html(r.sales_invoice || "")}</a></li>`
		)
		.join("");

	return `<div class="alert alert-info" style="margin-bottom:12px;">
		<b>${__("Already billed")}</b>
		<ul style="margin:6px 0 0 16px;padding:0;">${items}</ul>
	</div>`;
}
