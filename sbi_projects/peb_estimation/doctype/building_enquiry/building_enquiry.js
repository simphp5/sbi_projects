// Copyright (c) 2026, Velmaska and contributors
// For license information, please see license.txt

frappe.ui.form.on("Building Enquiry", {
	setup(frm) {
		// Only Approved templates can be picked
		frm.set_query("parameter_template", () => ({
			filters: { status: "Approved" },
		}));
	},

	refresh(frm) {
		frm.trigger("set_indicator");

		if (frm.is_new()) return;

		// Load parameters from the chosen approved template
		if (frm.doc.input_mode === "SBI Parameters") {
			frm.add_custom_button(__("Load from Template"), () => {
				frm.trigger("load_from_template", false);
			}).addClass("btn-primary");

			if ((frm.doc.parameters || []).length) {
				frm.add_custom_button(__("Reload (Replace All)"), () => {
					frappe.confirm(
						__("This clears the current answers and reloads the template. Continue?"),
						() => frm.trigger("load_from_template", true)
					);
				});
			}
		}

		// Progress hint for parameter mode
		if (frm.doc.input_mode === "SBI Parameters" && frm.doc.total_parameters) {
			const pending = frm.doc.mandatory_pending || 0;
			frm.dashboard.add_indicator(
				__("Filled {0} / {1}  ·  Mandatory pending: {2}", [
					frm.doc.filled_parameters || 0,
					frm.doc.total_parameters,
					pending,
				]),
				pending ? "orange" : "green"
			);
		}

		// Portal link actions (Phase 2B wires the actual sending)
		if (["Draft", "Sent to Client"].includes(frm.doc.status)) {
			frm.add_custom_button(
				__("Send Link to Client"),
				() => frm.trigger("send_link"),
				__("Portal")
			);
		}
	},

	set_indicator(frm) {
		const map = {
			Draft: "red",
			"Sent to Client": "blue",
			"Client Submitted": "purple",
			"Under Review": "orange",
			"Costing in Progress": "yellow",
			Quoted: "green",
			Won: "green",
			Lost: "grey",
		};
		if (frm.doc.status) {
			frm.page.set_indicator(__(frm.doc.status), map[frm.doc.status] || "blue");
		}
	},

	input_mode(frm) {
		if (frm.doc.input_mode === "SBI Parameters" && !frm.doc.parameter_template) {
			frappe.show_alert({
				message: __("Pick an Approved Parameter Template, then Load from Template."),
				indicator: "blue",
			});
		}
	},

	load_from_template(frm, replace = false) {
		if (!frm.doc.parameter_template) {
			frappe.msgprint({
				title: __("Template Required"),
				message: __("Select an Approved Parameter Template first."),
				indicator: "orange",
			});
			return;
		}
		frm.call({
			doc: frm.doc,
			method: "load_from_template",
			args: { template: frm.doc.parameter_template, replace: replace ? 1 : 0 },
			freeze: true,
			freeze_message: __("Loading parameters..."),
			callback(r) {
				frm.refresh_field("parameters");
				frm.dirty();
				frappe.show_alert({
					message: __("{0} parameter(s) added.", [r.message || 0]),
					indicator: r.message ? "green" : "orange",
				});
			},
		});
	},

	send_link(frm) {
		// Phase 2B replaces this stub with the real OTP + email flow.
		frappe.msgprint({
			title: __("Coming in Phase 2B"),
			message: __(
				"Client portal link generation (secure token + email OTP) is delivered in Phase 2B. " +
				"This enquiry is ready to hold parameter, BOQ, and drawing data now."
			),
			indicator: "blue",
		});
	},
});
