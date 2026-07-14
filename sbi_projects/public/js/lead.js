// Copyright (c) 2026, Velmaska and contributors
// Civil / PEB sales pipeline helpers on the Lead form.

frappe.ui.form.on("Lead", {
	refresh(frm) {
		set_stage_indicator(frm);
		if (frm.is_new()) return;

		frm.add_custom_button(__("Log Activity"), () => quick_log(frm));

		if (frm.doc.sbi_next_followup) {
			const overdue =
				frappe.datetime.get_diff(frappe.datetime.get_today(), frm.doc.sbi_next_followup) > 0;
			frm.dashboard.add_indicator(
				__("Follow-up: {0}", [frappe.datetime.str_to_user(frm.doc.sbi_next_followup)]),
				overdue ? "red" : "blue"
			);
		}
	},

	sbi_lead_stage(frm) {
		set_stage_indicator(frm);
	},
});

function set_stage_indicator(frm) {
	if (!frm.doc.sbi_lead_stage) return;
	frappe.db
		.get_value("Lead Stage", frm.doc.sbi_lead_stage, "indicator_color")
		.then((r) => {
			const colour = (r.message && r.message.indicator_color) || "blue";
			frm.dashboard.set_headline_alert(
				`<div class="row">
					<div class="col-xs-12">
						<span class="indicator ${colour.toLowerCase()}">
							${frappe.utils.escape_html(frm.doc.sbi_lead_stage)}
						</span>
					</div>
				</div>`
			);
		});
}

function quick_log(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Log Activity"),
		fields: [
			{
				fieldname: "activity_type",
				label: __("Activity"),
				fieldtype: "Link",
				options: "Lead Activity Type",
				reqd: 1,
				get_query: () => ({ filters: { is_active: 1 } }),
			},
			{
				fieldname: "activity_date",
				label: __("Date"),
				fieldtype: "Date",
				default: frappe.datetime.get_today(),
				reqd: 1,
			},
			{ fieldname: "remarks", label: __("Remarks / Outcome"), fieldtype: "Small Text" },
			{ fieldtype: "Section Break" },
			{ fieldname: "next_action", label: __("Next Action"), fieldtype: "Data" },
			{ fieldname: "next_action_date", label: __("Next Action Date"), fieldtype: "Date" },
		],
		primary_action_label: __("Log"),
		primary_action(values) {
			frappe.call({
				method: "sbi_projects.sbi_projects.lead_hooks.log_activity",
				args: Object.assign({ lead: frm.doc.name }, values),
				freeze: true,
				callback: (r) => {
					d.hide();
					frm.reload_doc();
					if (r.message) {
						frappe.show_alert({
							message: __("Stage moved to {0}", [r.message]),
							indicator: "green",
						});
					}
				},
			});
		},
	});
	d.show();
}
