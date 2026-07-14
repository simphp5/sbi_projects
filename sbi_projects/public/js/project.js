// Copyright (c) 2026, Velmaska and contributors
// Site Management helpers on the standard Project form.

frappe.ui.form.on("Project", {
	refresh(frm) {
		if (frm.is_new()) return;

		// ---- Create buttons ----
		frm.add_custom_button(__("BOQ"), () => {
			frappe.new_doc("BOQ", { project: frm.doc.name, customer: frm.doc.customer });
		}, __("Create"));

		if (!frm.doc.sbi_site_warehouse) {
			frm.add_custom_button(__("Site Warehouse"), () => {
				frappe.new_doc("Warehouse", {
					warehouse_name: frm.doc.project_name,
					company: frm.doc.company,
				});
			}, __("Create"));
		}

		// ---- Stage generation (for projects that have no tasks yet) ----
		frappe.db.count("Task", { filters: { project: frm.doc.name } }).then((n) => {
			if (n) return;

			if (frm.doc.sales_order) {
				frm.add_custom_button(__("Stages from Sales Order"), () => {
					call_stage_builder(frm, "create_stages_from_sales_order");
				}, __("Create"));
			}
			if (frm.doc.sbi_project_template) {
				frm.add_custom_button(__("Stages from Template"), () => {
					call_stage_builder(frm, "create_stages_from_template");
				}, __("Create"));
			}
		});

		// ---- Stage budget vs actual ----
		frm.add_custom_button(__("Stage Summary"), () => show_stage_summary(frm));

		if (frm.doc.sbi_boq) {
			frm.add_custom_button(__("View BOQ"), () => {
				frappe.set_route("Form", "BOQ", frm.doc.sbi_boq);
			});
		}
	},

	sales_order(frm) {
		if (frm.doc.sales_order && frm.is_new()) {
			frappe.show_alert({
				message: __("Stages will be built from the Sales Order payment schedule on save."),
				indicator: "blue",
			});
		}
	},
});

function call_stage_builder(frm, method) {
	frappe.call({
		method: `sbi_projects.sbi_projects.project_hooks.${method}`,
		args: { project: frm.doc.name },
		freeze: true,
		freeze_message: __("Creating stages..."),
		callback: () => frm.reload_doc(),
	});
}

function show_stage_summary(frm) {
	frappe.call({
		method: "sbi_projects.sbi_projects.project_hooks.get_stage_summary",
		args: { project: frm.doc.name },
		freeze: true,
		callback: (r) => {
			const rows = r.message || [];
			if (!rows.length) {
				frappe.msgprint(__("No stages found for this project."));
				return;
			}

			const fmt = (v) => format_currency(v, frm.doc.currency);
			let body = `
				<table class="table table-bordered" style="font-size:12px">
					<thead>
						<tr>
							<th>Stage</th>
							<th class="text-right">Wt %</th>
							<th>Due</th>
							<th class="text-right">Budget</th>
							<th class="text-right">BOQ</th>
							<th class="text-right">Variance</th>
							<th class="text-right">Progress</th>
						</tr>
					</thead>
					<tbody>`;

			let tb = 0, tq = 0;
			rows.forEach((d) => {
				tb += d.budget;
				tq += d.boq_estimate;
				const colour = d.variance < 0 ? "red" : "green";
				body += `
					<tr>
						<td><a href="/app/task/${d.task}">${frappe.utils.escape_html(d.stage)}</a></td>
						<td class="text-right">${d.weight}</td>
						<td>${d.due_date ? frappe.datetime.str_to_user(d.due_date) : "-"}</td>
						<td class="text-right">${fmt(d.budget)}</td>
						<td class="text-right">${fmt(d.boq_estimate)}</td>
						<td class="text-right" style="color:${colour}">${fmt(d.variance)}</td>
						<td class="text-right">${d.progress}%</td>
					</tr>`;
			});

			body += `
					</tbody>
					<tfoot>
						<tr style="font-weight:600">
							<td colspan="3">Total</td>
							<td class="text-right">${fmt(tb)}</td>
							<td class="text-right">${fmt(tq)}</td>
							<td class="text-right">${fmt(tb - tq)}</td>
							<td></td>
						</tr>
					</tfoot>
				</table>`;

			new frappe.ui.Dialog({
				title: __("Stage Budget vs BOQ"),
				size: "large",
				fields: [{ fieldtype: "HTML", options: body }],
			}).show();
		},
	});
}
