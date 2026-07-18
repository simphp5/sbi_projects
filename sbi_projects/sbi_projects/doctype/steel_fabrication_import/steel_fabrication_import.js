// Copyright (c) 2026, Velmaska and contributors

frappe.ui.form.on("Steel Fabrication Import", {
	refresh(frm) {
		frm.disable_save = false;

		if (frm.is_new()) {
			frm.dashboard.set_headline(
				__("Fill Job No, Company, Supplier and attach the Tekla Steel BOM, then Save and click Process.")
			);
			return;
		}

		// Process button (primary action)
		frm.add_custom_button(__("Process BOM"), () => {
			if (!frm.doc.bom_file) {
				frappe.msgprint(__("Attach the Steel BOM file first."));
				return;
			}
			frappe.confirm(
				__("Generate Items, BOMs, Subcontracting BOMs{0} for {1}?", [
					frm.doc.supplier ? __(" and a draft PO") : "",
					frm.doc.job_no,
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
				__("Processed: {0} MT | {1} RM | {2} FG | {3} bolts.{4}", [
					frm.doc.total_weight_mt,
					frm.doc.rm_count,
					frm.doc.fg_count,
					frm.doc.bolt_nos,
					frm.doc.created_po ? __(" Draft PO: {0} (fill rate).", [frm.doc.created_po]) : "",
				])
			);
		}
	},
});

function run_process(frm) {
	frappe.dom.freeze(__("Processing Steel BOM — creating items, BOMs, PO..."));
	frappe.call({
		method: "sbi_projects.sbi_projects.doctype.steel_fabrication_import.steel_fabrication_import.process_import",
		args: { docname: frm.doc.name },
		callback(r) {
			frappe.dom.unfreeze();
			frm.reload_doc();
			if (r.message && r.message.status === "ok") {
				frappe.show_alert({ message: __("Done — data generated."), indicator: "green" });
			}
		},
		error() {
			frappe.dom.unfreeze();
		},
	});
}
