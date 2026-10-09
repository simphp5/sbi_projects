// Copyright (c) 2026, Velmaska and contributors
frappe.ui.form.on("Tally Sync Log", {
	refresh(frm) {
		const d = frm.doc;
		if (d.direction === "Import" && d.record_type === "Voucher" && d.status === "Skipped") {
			frm.add_custom_button(__("Import Anyway"), () => {
				frappe.confirm(
					__("This Tally voucher was skipped because it looks like {0} {1}, already in ERPNext. Import it as a separate Journal Entry on the next sync?",
						[d.reference_doctype || "", d.reference_name || ""]),
					() => frappe.call({
						method: "sbi_projects.tally.admin.import_anyway",
						args: { log_name: d.name },
						freeze: true,
					}).then(() => {
						frappe.show_alert({ message: __("Will be imported on the next sync"), indicator: "green" });
						frm.reload_doc();
					})
				);
			}).addClass("btn-primary");
		}
	},
});
