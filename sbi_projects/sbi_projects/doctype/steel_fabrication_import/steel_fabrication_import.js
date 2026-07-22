// Copyright (c) 2026, Velmaska and contributors

frappe.ui.form.on("Steel Fabrication Import", {
	refresh(frm) {
		frm.disable_save = false;

		if (frm.is_new()) {
			frm.dashboard.set_headline(
				__("Enter PO No, Project, Company, Supplier; attach the Tekla Steel BOM; Save, then Process BOM.")
			);
			return;
		}

		frm.add_custom_button(__("Process BOM"), () => {
			if (!frm.doc.bom_file) {
				frappe.msgprint(__("Attach the Steel BOM file first."));
				return;
			}
			frappe.confirm(
				__("Generate category items{0} and the annexure for {1}?", [
					frm.doc.supplier ? __(" and a draft PO") : "",
					frm.doc.po_no,
				]),
				() => run_process(frm)
			);
		}).addClass("btn-primary");

		if (frm.doc.created_po) {
			frm.add_custom_button(__("Open Draft PO"), () => {
				frappe.set_route("Form", "Purchase Order", frm.doc.created_po);
			});
		}

		if (frm.doc.status === "Processed") {
			frm.dashboard.set_headline(
				__("Processed: {0} MT across {1} categories.{2} Next: fill Rate/kg, submit PO, then GRN at site.", [
					frm.doc.total_weight_mt,
					frm.doc.category_count,
					frm.doc.created_po ? __(" Draft PO: {0}.", [frm.doc.created_po]) : "",
				])
			);
		}
	},
});

function run_process(frm) {
	frappe.dom.freeze(__("Processing - creating category items, PO and annexure..."));
	frappe.call({
		method: "sbi_projects.sbi_projects.doctype.steel_fabrication_import.steel_fabrication_import.process_import",
		args: { docname: frm.doc.name },
		callback(r) {
			frappe.dom.unfreeze();
			frm.reload_doc();
			if (r.message && r.message.status === "ok") {
				frappe.show_alert({ message: __("Done - data generated."), indicator: "green" });
			}
		},
		error() {
			frappe.dom.unfreeze();
		},
	});
}
