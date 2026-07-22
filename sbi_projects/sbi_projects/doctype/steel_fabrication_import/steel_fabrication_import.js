// Copyright (c) 2026, Velmaska and contributors

frappe.ui.form.on("Steel Fabrication Import", {
	project(frm) {
		if (!frm.doc.project) return;
		// fetch the project's site warehouse and prefill the receiving warehouse
		frappe.db.get_value("Project", frm.doc.project, ["project_name", "cost_center"]).then((r) => {
			const pname = r.message && r.message.project_name;
			if (!pname) return;
			frappe.db.get_value("Company", frm.doc.company || frappe.defaults.get_user_default("Company"), "abbr").then((c) => {
				const abbr = c.message && c.message.abbr;
				if (!abbr) return;
				const wh = `${pname} - ${abbr}`;
				frappe.db.exists("Warehouse", wh).then((exists) => {
					if (exists) frm.set_value("target_warehouse", wh);
				});
			});
		});
	},

	refresh(frm) {
		frm.disable_save = false;

		if (frm.is_new()) {
			frm.dashboard.set_headline(
				__("Select Project + Company, attach the Tekla Steel BOM, Save, then Process BOM. One draft PO is created per material category.")
			);
			return;
		}

		frm.add_custom_button(__("Process BOM"), () => {
			if (!frm.doc.bom_file) {
				frappe.msgprint(__("Attach the Steel BOM file first."));
				return;
			}
			frappe.confirm(
				__("Generate one draft PO per category for {0}?", [frm.doc.name]),
				() => run_process(frm)
			);
		}).addClass("btn-primary");

		if (frm.doc.status === "Processed") {
			frm.dashboard.set_headline(
				__("Processed: {0} MT, {1} POs created. Open each PO, set Supplier + Rate/kg, then print with the 'Fabrication PO' format for the annexure.", [
					frm.doc.total_weight_mt,
					frm.doc.po_count,
				])
			);
		}
	},
});

function run_process(frm) {
	frappe.dom.freeze(__("Processing - creating items, per-category POs and annexures..."));
	frappe.call({
		method: "sbi_projects.sbi_projects.doctype.steel_fabrication_import.steel_fabrication_import.process_import",
		args: { docname: frm.doc.name },
		callback(r) {
			frappe.dom.unfreeze();
			frm.reload_doc();
			if (r.message && r.message.status === "ok") {
				frappe.show_alert({
					message: __("Done - {0} POs created.", [r.message.po_count]),
					indicator: "green",
				});
			}
		},
		error() {
			frappe.dom.unfreeze();
		},
	});
}