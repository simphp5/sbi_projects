// Copyright (c) 2026, Velmaska and contributors
// Sales Order client script:
//   * Create -> Project (with Stages)  — one project per SO, guarded
//   * View Project  — shown once a project already exists for this SO
//   * validate: warn if payment schedule rows have no project stage mapped
//
// The milestone-invoice button lives in sales_order_milestone.js and is not
// touched here.

frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;
		sbi_project_button(frm);
	},

	validate(frm) {
		const rows = frm.doc.payment_schedule || [];
		const unmapped = rows.filter((d) => !d.sbi_stage);
		if (unmapped.length && rows.length) {
			frappe.show_alert({
				message: __("{0} payment rows have no Project Stage mapped.", [unmapped.length]),
				indicator: "orange",
			});
		}
	},
});

function sbi_project_button(frm) {
	// Is there already a project for this Sales Order?
	frappe.db.get_value(
		"Project",
		{ sales_order: frm.doc.name },
		"name",
		(r) => {
			const existing = r && r.name;

			if (existing) {
				// project exists -> offer to open it, do not allow a duplicate
				frm.add_custom_button(
					__("View Project"),
					() => frappe.set_route("Form", "Project", existing),
					__("Create")
				);
			} else {
				frm.add_custom_button(
					__("Project (with Stages)"),
					() => sbi_create_project_dialog(frm),
					__("Create")
				);
			}
		}
	);
}

function sbi_create_project_dialog(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Create Project from Sales Order"),
		fields: [
			{
				fieldname: "project_name",
				label: __("Project Name"),
				fieldtype: "Data",
				reqd: 1,
				default: frm.doc.customer_name || frm.doc.customer || frm.doc.name,
				description: __("Site cost center and warehouse are created automatically."),
			},
			{
				fieldname: "expected_start_date",
				label: __("Expected Start Date"),
				fieldtype: "Date",
				default: frappe.datetime.get_today(),
			},
		],
		primary_action_label: __("Create"),
		primary_action(values) {
			d.hide();
			// Re-check right before creating, in case one was made in another tab.
			frappe.db.get_value(
				"Project",
				{ sales_order: frm.doc.name },
				"name",
				(r) => {
					if (r && r.name) {
						frappe.msgprint({
							title: __("Project already exists"),
							message: __("Project {0} is already linked to this Sales Order.", [r.name]),
							indicator: "orange",
						});
						frm.refresh();
						return;
					}
					sbi_insert_project(frm, values);
				}
			);
		},
	});
	d.show();
}

function sbi_insert_project(frm, values) {
	frappe.call({
		method: "frappe.client.insert",
		args: {
			doc: {
				doctype: "Project",
				project_name: values.project_name,
				customer: frm.doc.customer,
				sales_order: frm.doc.name,
				company: frm.doc.company,
				expected_start_date:
					values.expected_start_date || frappe.datetime.get_today(),
			},
		},
		freeze: true,
		freeze_message: __("Creating project, stages and site cost center..."),
		callback(r) {
			if (!r.message) return;
			frappe.show_alert({
				message: __("Project {0} created", [r.message.name]),
				indicator: "green",
			});
			frappe.set_route("Form", "Project", r.message.name);
		},
	});
}
