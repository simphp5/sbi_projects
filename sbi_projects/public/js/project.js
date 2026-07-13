// Copyright (c) 2026, Velmaska and contributors
// Adds Site Management helpers to the standard Project form.

frappe.ui.form.on("Project", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("BOQ"), () => {
			frappe.new_doc("BOQ", { project: frm.doc.name, customer: frm.doc.customer });
		}, __("Create"));

		if (!frm.doc.sbi_site_warehouse) {
			frm.add_custom_button(__("Site Warehouse"), () => {
				frappe.new_doc("Warehouse", {
					warehouse_name: frm.doc.project_name,
					company: frm.doc.company,
				});
			}, __("Create"));
		}

		if (frm.doc.sbi_boq) {
			frm.add_custom_button(__("View BOQ"), () => {
				frappe.set_route("Form", "BOQ", frm.doc.sbi_boq);
			});
		}
	},

	sbi_project_template(frm) {
		if (frm.doc.sbi_project_template && frm.is_new()) {
			frappe.show_alert({
				message: __("Stage tasks will be created after you save."),
				indicator: "blue",
			});
		}
	},
});
