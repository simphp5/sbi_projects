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
			return;
		}

		if (!frm.is_new()) {
			frm.add_custom_button(__("Load Parameters"), () => {
				frm.trigger("load_parameters");
			}).addClass("btn-primary");

			if ((frm.doc.parameters || []).length) {
				frm.add_custom_button(__("Reload (Replace All)"), () => {
					frappe.confirm(
						__("This will clear the current rows and reload every parameter for {0}. Continue?", [
							frm.doc.work_type,
						]),
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
			frappe.msgprint({
				title: __("Work Type Changed"),
				message: __("Click Reload (Replace All) to refresh the parameter list."),
				indicator: "orange",
			});
		}
	},

	load_parameters(frm, replace = false) {
		if (!frm.doc.work_type) {
			frappe.msgprint(__("Set Work Type first."));
			return;
		}
		frm.call({
			doc: frm.doc,
			method: "load_parameters",
			args: { replace: replace ? 1 : 0 },
			freeze: true,
			freeze_message: __("Loading parameters..."),
			callback(r) {
				frm.refresh_field("parameters");
				frappe.show_alert({
					message: __("{0} parameter(s) added.", [r.message || 0]),
					indicator: r.message ? "green" : "orange",
				});
			},
		});
	},
});
