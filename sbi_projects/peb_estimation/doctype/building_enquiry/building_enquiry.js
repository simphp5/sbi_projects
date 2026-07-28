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

		if (frm.doc.client_chooses_work_type) {
			frm.dashboard.add_comment(
				__("The client will choose the Work Type on the portal. The Work Type set here is only a starting suggestion."),
				"blue",
				true
			);
		}

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

		// Portal link actions
		if (["Draft", "Sent to Client", "Client Submitted", "Under Review"].includes(frm.doc.status)) {
			frm.add_custom_button(
				frm.doc.access_token ? __("Resend Link") : __("Send Link to Client"),
				() => frm.trigger("send_link"),
				__("Portal")
			);
		}
		if (frm.doc.access_token) {
			frm.add_custom_button(__("Extend Link"), () => frm.trigger("extend_link"), __("Portal"));
			frm.add_custom_button(__("Copy Link"), () => frm.trigger("copy_link"), __("Portal"));
		}

		// Highlight rows the client changed (override-with-audit)
		const changed = (frm.doc.parameters || []).filter((r) => r.value_changed);
		if (changed.length) {
			frm.dashboard.add_indicator(
				__("{0} value(s) changed by client", [changed.length]),
				"orange"
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
		if (frm.is_dirty()) {
			frappe.msgprint(__("Please save the enquiry before sending the link."));
			return;
		}
		const d = new frappe.ui.Dialog({
			title: __("Send Link to Client"),
			fields: [
				{
					fieldname: "valid_days",
					label: __("Link Valid (days)"),
					fieldtype: "Int",
					default: frm.doc.link_valid_days || 15,
					reqd: 1,
				},
				{
					fieldname: "send_email",
					label: __("Email the link to {0}", [frm.doc.contact_email || __("client")]),
					fieldtype: "Check",
					default: 1,
				},
				{
					fieldname: "note",
					fieldtype: "HTML",
					options:
						"<p class='text-muted small'>A fresh secure link is generated. Any previously sent link stops working.</p>",
				},
			],
			primary_action_label: __("Generate & Send"),
			primary_action(values) {
				frm.call({
					doc: frm.doc,
					method: "generate_link",
					args: { valid_days: values.valid_days, send_email: values.send_email ? 1 : 0 },
					freeze: true,
					freeze_message: __("Generating link..."),
					callback(r) {
						d.hide();
						frm.reload_doc();
						if (r.message && r.message.url) {
							frappe.msgprint({
								title: __("Link Ready"),
								message: __(
									"Valid until <b>{0}</b>.<br><br><a href='{1}' target='_blank'>{1}</a>",
									[r.message.expires_on, r.message.url]
								),
								indicator: "green",
							});
						}
					},
				});
			},
		});
		d.show();
	},

	extend_link(frm) {
		frappe.prompt(
			{
				fieldname: "extra_days",
				label: __("Extend by (days)"),
				fieldtype: "Int",
				default: 15,
				reqd: 1,
			},
			(values) => {
				frm.call({
					doc: frm.doc,
					method: "extend_link",
					args: { extra_days: values.extra_days },
					freeze: true,
					callback(r) {
						frm.reload_doc();
						frappe.show_alert({
							message: __("Link now valid until {0}", [r.message.expires_on]),
							indicator: "green",
						});
					},
				});
			},
			__("Extend Link"),
			__("Extend")
		);
	},

	copy_link(frm) {
		const url =
			frappe.urllib.get_base_url() +
			"/building_enquiry?id=" +
			encodeURIComponent(frm.doc.name) +
			"&key=" +
			encodeURIComponent(frm.doc.access_token);
		frappe.utils.copy_to_clipboard(url);
		frappe.show_alert({ message: __("Link copied"), indicator: "green" });
	},
});
