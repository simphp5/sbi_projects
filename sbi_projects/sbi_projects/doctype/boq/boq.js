// Copyright (c) 2026, Velmaska and contributors

frappe.ui.form.on("BOQ", {
	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.status !== "Revised") {
			frm.add_custom_button(__("Create Revision"), () => {
				frappe.call({
					method: "sbi_projects.sbi_projects.doctype.boq.boq.make_revision",
					args: { boq: frm.doc.name },
					freeze: true,
					callback: (r) => {
						if (r.message) frappe.set_route("Form", "BOQ", r.message);
					},
				});
			});

			if (frm.doc.status === "Submitted") {
				frm.add_custom_button(__("Mark Approved"), () => {
					frm.set_value("status", "Approved");
					frm.save("Update");
				});
			}
		}
	},

	boq_template(frm) {
		if (!frm.doc.boq_template) return;

		if ((frm.doc.items || []).length) {
			frappe.confirm(
				__("This will replace the existing items. Continue?"),
				() => load_template(frm)
			);
		} else {
			load_template(frm);
		}
	},
});

function load_template(frm) {
	frappe.call({
		method: "sbi_projects.sbi_projects.doctype.boq.boq.get_template_items",
		args: { boq_template: frm.doc.boq_template },
		freeze: true,
		freeze_message: __("Loading template items..."),
		callback: (r) => {
			if (!r.message) return;
			frm.clear_table("items");
			r.message.forEach((row) => {
				const child = frm.add_child("items");
				Object.assign(child, row);
			});
			frm.refresh_field("items");
			recalc(frm);
			frappe.show_alert({
				message: __("{0} items loaded", [r.message.length]),
				indicator: "green",
			});
		},
	});
}

function recalc(frm) {
	let total = 0,
		qty = 0;
	(frm.doc.items || []).forEach((d) => {
		d.amount = flt(d.qty) * flt(d.rate);
		total += d.amount;
		qty += flt(d.qty);
	});
	frm.set_value("total_amount", total);
	frm.set_value("total_qty", qty);
	frm.refresh_field("items");
}

frappe.ui.form.on("BOQ Item", {
	qty: (frm) => recalc(frm),
	rate: (frm) => recalc(frm),
	items_remove: (frm) => recalc(frm),
});
