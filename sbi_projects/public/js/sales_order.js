// Copyright (c) 2026, Velmaska and contributors
// Warn if payment schedule rows have no project stage mapped.

frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;

		frm.add_custom_button(__("Project (with Stages)"), () => {
			frappe.new_doc("Project", {
				project_name: frm.doc.name,
				customer: frm.doc.customer,
				sales_order: frm.doc.name,
				company: frm.doc.company,
				expected_start_date: frappe.datetime.get_today(),
			});
		}, __("Create"));
	},

	validate(frm) {
		const unmapped = (frm.doc.payment_schedule || []).filter((d) => !d.sbi_stage);
		if (unmapped.length && (frm.doc.payment_schedule || []).length) {
			frappe.show_alert({
				message: __("{0} payment rows have no Project Stage mapped.", [unmapped.length]),
				indicator: "orange",
			});
		}
	},
});
