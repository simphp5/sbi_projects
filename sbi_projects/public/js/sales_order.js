// Copyright (c) 2026, Velmaska and contributors
// Sales Order client script:
//   * remove ERPNext's core "Project" create button (avoids a blank, unlinked project)
//   * Create -> Project (with Stages)  — one project per SO, guarded, dialog
//   * View Project (new tab) once a project already exists for this SO
//   * mapped-project caption under Delivery Date (link opens in a new tab,
//     or "No project created for this order")
//   * Print button opens in a new tab
//   * validate: warn if payment schedule rows have no project stage mapped
//
// The milestone-invoice button lives in sales_order_milestone.js and is not
// touched here. Core Create buttons (Delivery Note, Sales Invoice, ...) are left
// on standard same-tab behaviour because they carry mapped data.

frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) {
			sbi_render_mapped_project(frm, null);
			return;
		}

		// 1. drop ERPNext's own "Project" button to avoid confusion
		frm.remove_custom_button("Project", "Create");

		// 2. our Create/View Project button + mapped-project caption
		sbi_project_button(frm);

		// 3. Print in a new tab
		sbi_print_in_new_tab(frm);
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

// ---------------------------------------------------------------------------
// Create / View Project
// ---------------------------------------------------------------------------

function sbi_project_button(frm) {
	frappe.db.get_value("Project", { sales_order: frm.doc.name }, "name", (r) => {
		const existing = r && r.name;
		sbi_render_mapped_project(frm, existing);

		if (existing) {
			frm.add_custom_button(
				__("View Project"),
				() => sbi_open_new_tab(`/app/project/${encodeURIComponent(existing)}`),
				__("Create")
			);
		} else {
			frm.add_custom_button(
				__("Project (with Stages)"),
				() => sbi_create_project_dialog(frm),
				__("Create")
			);
		}
	});
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
			frappe.db.get_value("Project", { sales_order: frm.doc.name }, "name", (r) => {
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
			});
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
				expected_start_date: values.expected_start_date || frappe.datetime.get_today(),
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
			sbi_open_new_tab(`/app/project/${encodeURIComponent(r.message.name)}`);
			frm.refresh();
		},
	});
}

// ---------------------------------------------------------------------------
// Mapped-project caption under Delivery Date
// ---------------------------------------------------------------------------

function sbi_render_mapped_project(frm, project) {
	const wrapper = frm.get_field("sbi_mapped_project");
	if (!wrapper || !wrapper.$wrapper) return;

	let html;
	if (project) {
		const url = `/app/project/${encodeURIComponent(project)}`;
		html =
			`<a href="${url}" target="_blank" rel="noopener" ` +
			`class="text-primary" style="font-weight:600;">` +
			`${frappe.utils.escape_html(project)} \u2197</a>`;
	} else {
		html =
			`<span class="text-muted">${__("No project created for this order")}</span>`;
	}
	wrapper.$wrapper.html(
		`<div class="form-group"><label class="control-label">${__("Project")}</label>` +
		`<div class="control-value" style="padding-top:3px;">${html}</div></div>`
	);
}

// ---------------------------------------------------------------------------
// Print in a new tab
// ---------------------------------------------------------------------------

function sbi_print_in_new_tab(frm) {
	frm.page.add_menu_item(__("Print (new tab)"), () => {
		const url =
			`/app/print/${encodeURIComponent(frm.doctype)}/` +
			`${encodeURIComponent(frm.docname)}`;
		sbi_open_new_tab(url);
	});
}

// ---------------------------------------------------------------------------

function sbi_open_new_tab(url) {
	window.open(url, "_blank", "noopener");
}
