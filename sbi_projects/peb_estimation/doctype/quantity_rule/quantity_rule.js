// Copyright (c) 2026, Velmaska and contributors
// For license information, please see license.txt

frappe.ui.form.on("Quantity Rule", {
	refresh(frm) {
		frm.trigger("payment_terms_template");
	},

	payment_terms_template(frm) {
		// Offer the template's terms as the stage choices, so a rule can be tied
		// to the same vocabulary the Sales Order will eventually bill on.
		if (!frm.doc.payment_terms_template) {
			frm.set_df_property("stage", "options", "");
			frm.set_df_property("stage", "fieldtype", "Data");
			frm.refresh_field("stage");
			return;
		}
		frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Payment Terms Template Detail",
				filters: { parent: frm.doc.payment_terms_template },
				fields: ["payment_term", "description", "idx"],
				order_by: "idx asc",
				parent: "Payment Terms Template",
				limit_page_length: 0,
			},
			callback(r) {
				const terms = (r.message || [])
					.map((t) => t.payment_term || t.description)
					.filter(Boolean);
				if (!terms.length) return;
				frm.set_df_property("stage", "fieldtype", "Select");
				frm.set_df_property("stage", "options", [""].concat(terms).join("\n"));
				frm.refresh_field("stage");
			},
		});
	},
});
