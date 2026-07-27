// Copyright (c) 2026, Velmaska and contributors
// For license information, please see license.txt

frappe.ui.form.on("Building Parameter Template", {
	refresh(frm) {
		frm.trigger("set_indicator");

		if (frm.doc.status === "Approved") {
			frm.dashboard.add_comment(
				__("This template is approved and can be circulated to clients."),
				"green",
				true
			);
		}

		// Load Parameters is available even on a brand-new unsaved template,
		// as long as a Work Type is chosen. It fills the child table so the
		// user can then Save.
		if (frm.doc.status !== "Approved" && frm.doc.status !== "Inactive") {
			frm.add_custom_button(__("Load Parameters"), () => {
				frm.trigger("load_parameters", false);
			}).addClass("btn-primary");

			if ((frm.doc.parameters || []).length) {
				frm.add_custom_button(__("Reload (Replace All)"), () => {
					frappe.confirm(
						__(
							"This clears the current rows and reloads every parameter for {0}. Continue?",
							[frm.doc.work_type || __("this work type")]
						),
						() => frm.trigger("load_parameters", true)
					);
				});
			}
		}
	},

	set_indicator(frm) {
		const map = {
			Draft: "red",
			"Pending Approval": "orange",
			Approved: "green",
			Inactive: "grey",
		};
		if (frm.doc.status) {
			frm.page.set_indicator(__(frm.doc.status), map[frm.doc.status] || "blue");
		}
	},

	work_type(frm) {
		if (frm.doc.work_type && (frm.doc.parameters || []).length) {
			frappe.show_alert({
				message: __("Work Type changed. Use Reload (Replace All) to refresh."),
				indicator: "orange",
			});
		}
	},

	load_parameters(frm, replace = false) {
		if (!frm.doc.work_type) {
			frappe.msgprint({
				title: __("Work Type Required"),
				message: __("Select a Work Type before loading parameters."),
				indicator: "orange",
			});
			return;
		}

		// Stateless server call -- works on new (unsaved) and saved docs alike.
		frappe.call({
			method:
				"sbi_projects.peb_estimation.doctype.building_parameter.building_parameter.get_parameters_for_work_type",
			args: { work_type: frm.doc.work_type },
			freeze: true,
			freeze_message: __("Loading parameters..."),
			callback(r) {
				const rows = r.message || [];
				if (!rows.length) {
					frappe.msgprint(
						__("No active parameters found for {0}.", [frm.doc.work_type])
					);
					return;
				}

				if (replace) {
					frm.clear_table("parameters");
				}

				const existing = new Set(
					(frm.doc.parameters || []).map((d) => d.parameter)
				);

				let added = 0;
				rows.forEach((row) => {
					if (existing.has(row.parameter)) return;
					const child = frm.add_child("parameters", {
						parameter: row.parameter,
						parameter_name: row.parameter_name,
						section: row.section,
						uom: row.uom,
						fieldtype: row.fieldtype,
						is_mandatory: row.is_mandatory,
						display_order: row.display_order,
					});
					existing.add(row.parameter);
					added += 1;
				});

				frm.refresh_field("parameters");
				frappe.show_alert({
					message: __("{0} parameter(s) added.", [added]),
					indicator: added ? "green" : "orange",
				});
			},
		});
	},
});
