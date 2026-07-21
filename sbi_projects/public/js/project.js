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

// ---------------------------------------------------------------------------
// Stage tree on the Project form.
//
// Frappe merges multiple handlers for the same doctype, so this block sits
// alongside whatever else this file already defines for Project.
// ---------------------------------------------------------------------------

frappe.ui.form.on("Project", {
	refresh(frm) {
		if (frm.is_new()) return;
		sbi_render_stage_tree(frm);
	},
});

function sbi_render_stage_tree(frm) {
	const wrapper = frm.get_field("sbi_stages_html");
	if (!wrapper || !wrapper.$wrapper) return;

	wrapper.$wrapper.html('<div class="text-muted" style="padding:12px">Loading stagesâ€¦</div>');

	frappe.call({
		method: "sbi_projects.sbi_projects.stage_tree.get_stage_tree",
		args: { project: frm.doc.name },
		callback(r) {
			const data = (r && r.message) || { stages: [], totals: {} };
			wrapper.$wrapper.html(sbi_stage_html(data, frm.doc.name));
			sbi_bind_stage_actions(wrapper.$wrapper, frm);
		},
		error() {
			wrapper.$wrapper.html(
				'<div class="text-muted" style="padding:12px">Stages could not be loaded.</div>'
			);
		},
	});
}

function sbi_money(v) {
	return format_currency(flt(v));
}

function sbi_stage_html(data, project) {
	const stages = data.stages || [];
	if (!stages.length) {
		return `
			<div style="border:1px solid var(--border-color);padding:22px;text-align:center">
				<div style="font-weight:600;margin-bottom:6px">No stages yet</div>
				<div class="text-muted" style="margin-bottom:14px">
					Link a submitted sales order, then use Create &rsaquo; Stages from Sales Order.
				</div>
				<button class="btn btn-sm btn-default sbi-refresh-stages">Refresh</button>
			</div>`;
	}

	const byParent = {};
	stages.forEach((t) => {
		const key = t.parent_task || "__root__";
		(byParent[key] = byParent[key] || []).push(t);
	});

	const t = data.totals || {};
	const varClass = flt(t.variance) < 0 ? "sbi-over" : "sbi-under";

	let html = `
		<style>
			.sbi-stages{border:1px solid var(--border-color);border-radius:4px;overflow:hidden}
			.sbi-stages-head{display:flex;gap:18px;align-items:baseline;padding:10px 14px;
				background:var(--fg-color);border-bottom:1px solid var(--border-color)}
			.sbi-stages-head b{font-size:13px}
			.sbi-stages-head span{font-size:12px;color:var(--text-muted)}
			.sbi-row{display:flex;align-items:center;gap:10px;padding:9px 14px;
				border-bottom:1px solid var(--border-color);font-size:13px}
			.sbi-row:last-child{border-bottom:0}
			.sbi-row.sbi-child{background:var(--subtle-fg);padding-left:40px}
			.sbi-name{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
			.sbi-name a{color:var(--text-color);font-weight:600}
			.sbi-row.sbi-child .sbi-name a{font-weight:400}
			.sbi-meta{font-size:11px;color:var(--text-muted);font-weight:400}
			.sbi-bar{width:74px;height:6px;background:var(--border-color);border-radius:3px;
				overflow:hidden;flex:0 0 auto}
			.sbi-bar i{display:block;height:100%;background:var(--text-color)}
			.sbi-pct{width:38px;text-align:right;font-variant-numeric:tabular-nums;
				font-size:12px;color:var(--text-muted);flex:0 0 auto}
			.sbi-money{width:112px;text-align:right;font-variant-numeric:tabular-nums;flex:0 0 auto}
			.sbi-over{color:#be1e2d}
			.sbi-under{color:#0f6b3f}
			.sbi-logs{flex:0 0 auto}
			.sbi-foot{display:flex;gap:8px;padding:10px 14px;background:var(--fg-color);
				border-top:1px solid var(--border-color)}
			@media (max-width:900px){.sbi-bar,.sbi-pct{display:none}}
		</style>
		<div class="sbi-stages">
			<div class="sbi-stages-head">
				<b>${stages.length} stage${stages.length === 1 ? "" : "s"}</b>
				<span>Budget ${sbi_money(t.budget)}</span>
				<span>Actual ${sbi_money(t.actual)}</span>
				<span class="${varClass}">Variance ${sbi_money(t.variance)}</span>
				<span style="margin-left:auto">${t.logs || 0} work log${t.logs === 1 ? "" : "s"}</span>
			</div>`;

	const row = (task, isChild) => {
		const pct = Math.round(flt(task.progress));
		const vClass = flt(task.variance) < 0 ? "sbi-over" : "";
		const due = task.exp_end_date
			? frappe.datetime.str_to_user(task.exp_end_date)
			: "";
		const meta = [task.status, due].filter(Boolean).join(" Â· ");
		return `
			<div class="sbi-row ${isChild ? "sbi-child" : ""}">
				<span class="sbi-name">
					<a href="/app/task/${encodeURIComponent(task.name)}">${frappe.utils.escape_html(task.subject || task.name)}</a>
					<span class="sbi-meta">&nbsp;${frappe.utils.escape_html(meta)}</span>
				</span>
				<span class="sbi-bar"><i style="width:${Math.min(pct, 100)}%"></i></span>
				<span class="sbi-pct">${pct}%</span>
				<span class="sbi-money">${sbi_money(task.budget)}</span>
				<span class="sbi-money ${vClass}">${sbi_money(task.actual)}</span>
				<span class="sbi-logs">
					<button class="btn btn-xs btn-default sbi-add-log" data-task="${task.name}">
						+ Log${task.log_count ? " (" + task.log_count + ")" : ""}
					</button>
				</span>
			</div>`;
	};

	(byParent["__root__"] || []).forEach((stage) => {
		html += row(stage, false);
		(byParent[stage.name] || []).forEach((child) => {
			html += row(child, true);
		});
	});

	html += `
			<div class="sbi-foot">
				<button class="btn btn-xs btn-default sbi-refresh-stages">Refresh</button>
				<button class="btn btn-xs btn-default sbi-open-tasks">Open in task tree</button>
			</div>
		</div>`;

	return html;
}

function sbi_bind_stage_actions($wrapper, frm) {
	$wrapper.find(".sbi-refresh-stages").on("click", () => sbi_render_stage_tree(frm));

	$wrapper.find(".sbi-open-tasks").on("click", () => {
		frappe.set_route("Tree", "Task", { project: frm.doc.name });
	});

	$wrapper.find(".sbi-add-log").on("click", function () {
		const task = $(this).attr("data-task");
		frappe.new_doc("Daily Work Log", {
			project: frm.doc.name,
			task: task,
			log_date: frappe.datetime.get_today(),
		});
	});
}

// ---------------------------------------------------------------------------
// Show net / GST / grand total as a clear summary on Quotation and Sales Order,
// so it is obvious the payment plan is on the net figure.
// ---------------------------------------------------------------------------

["Quotation", "Sales Order"].forEach(function (dt) {
	frappe.ui.form.on(dt, {
		refresh(frm) {
			sbi_render_totals(frm);
		},
		net_total(frm) { sbi_render_totals(frm); },
		grand_total(frm) { sbi_render_totals(frm); },
	});
});

function sbi_render_totals(frm) {
	const f = frm.get_field("sbi_totals_html");
	if (!f || !f.$wrapper) return;

	const net = flt(frm.doc.net_total);
	const tax = flt(frm.doc.total_taxes_and_charges);
	const grand = flt(frm.doc.grand_total) || flt(frm.doc.rounded_total);
	if (!net && !grand) { f.$wrapper.html(""); return; }

	f.$wrapper.html(`
		<div style="border:1px solid var(--border-color);border-radius:4px;overflow:hidden;max-width:360px">
			<div style="display:flex;justify-content:space-between;padding:8px 12px;border-bottom:1px solid var(--border-color)">
				<span class="text-muted">Net total (payment plan basis)</span>
				<b style="font-variant-numeric:tabular-nums">${format_currency(net)}</b>
			</div>
			<div style="display:flex;justify-content:space-between;padding:8px 12px;border-bottom:1px solid var(--border-color)">
				<span class="text-muted">GST</span>
				<span style="font-variant-numeric:tabular-nums">${format_currency(tax)}</span>
			</div>
			<div style="display:flex;justify-content:space-between;padding:8px 12px;background:var(--fg-color)">
				<span>Grand total</span>
				<b style="font-variant-numeric:tabular-nums">${format_currency(grand)}</b>
			</div>
		</div>`);
}
