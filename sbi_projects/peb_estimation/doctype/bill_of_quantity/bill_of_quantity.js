// Copyright (c) 2026, Velmaska and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bill of Quantity", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("Recalculate Rates (WA)"), () => {
			frm.call({
				doc: frm.doc,
				method: "recalculate_rates",
				freeze: true,
				freeze_message: __("Recalculating from Rate Card..."),
				callback(r) {
					frm.reload_doc();
					frappe.show_alert({
						message: __("{0} line(s) updated. Manual lines were left untouched.", [r.message || 0]),
						indicator: "green",
					});
				},
			});
		}).addClass("btn-primary");

		// stage-wise subtotal hint
		const byStage = {};
		(frm.doc.lines || []).forEach((l) => {
			const s = l.stage || __("Unassigned");
			byStage[s] = (byStage[s] || 0) + (l.amount || 0);
		});
		const stages = Object.keys(byStage);
		if (stages.length > 1) {
			frm.dashboard.add_comment(
				__("Stages: ") + stages.map((s) => s + " " + format_currency(byStage[s], frm.doc.currency)).join("  ·  "),
				"blue", true
			);
		}
	},
});

frappe.ui.form.on("Bill of Quantity Line", {
	rate(frm, cdt, cdn) {
		// SBI typed a rate manually -> flag as Manual so Recalculate won't overwrite it
		const row = locals[cdt][cdn];
		if (row.rate_source !== "Manual") {
			frappe.model.set_value(cdt, cdn, "rate_source", "Manual");
		}
		frappe.model.set_value(cdt, cdn, "amount", (row.qty || 0) * (row.rate || 0));
	},
	qty(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "amount", (row.qty || 0) * (row.rate || 0));
	},
	work_item(frm, cdt, cdn) {
		// new work item -> pull WA rate unless the row is already manual
		const row = locals[cdt][cdn];
		if (!row.work_item || row.rate_source === "Manual") return;
		frappe.call({
			method: "frappe.client.get",
			args: { doctype: "Work Item", name: row.work_item },
			callback() {
				// rate fetch happens on server Recalculate; here we just set category/uom
			},
		});
		frappe.db.get_value("Work Item", row.work_item, ["category", "uom"]).then((r) => {
			if (r && r.message) {
				frappe.model.set_value(cdt, cdn, "category", r.message.category);
				frappe.model.set_value(cdt, cdn, "uom", r.message.uom);
			}
		});
	},
});
