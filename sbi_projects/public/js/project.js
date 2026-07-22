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


// ---------------------------------------------------------------------------


// ---------------------------------------------------------------------------


// ---------------------------------------------------------------------------


// ---------------------------------------------------------------------------
// Stage tree + owner budget panel on the Project form.
//
// The stage tree shows budget, progress and actual per stage.  The +Log button
// and stage links open in a NEW TAB so the site manager can file a work log
// without losing the project they are looking at.  The budget panel lets the
// owner set the planned amount per account in one place.
//
// Cost figures here are for the office.  The mobile site app shows none of this.
// ---------------------------------------------------------------------------

frappe.ui.form.on("Project", {
	refresh(frm) {
		if (frm.is_new()) return;
		sbi_render_stage_tree(frm);
		sbi_render_budget_panel(frm);
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
			wrapper.$wrapper.html(sbi_stage_html(data));
			sbi_bind_stage_actions(wrapper.$wrapper, frm);
		},
		error() {
			wrapper.$wrapper.html('<div class="text-muted" style="padding:12px">Stages could not be loaded.</div>');
		},
	});
}

function sbi_money(v) { return format_currency(flt(v)); }

function sbi_stage_html(data) {
	const stages = data.stages || [];
	if (!stages.length) {
		return `<div style="border:1px solid var(--border-color);padding:22px;text-align:center">
			<div style="font-weight:600;margin-bottom:6px">No stages yet</div>
			<div class="text-muted" style="margin-bottom:14px">Link a submitted sales order, then use Create &rsaquo; Stages from Sales Order.</div>
			<button class="btn btn-sm btn-default sbi-refresh-stages">Refresh</button></div>`;
	}
	const byParent = {};
	stages.forEach((t) => { const k = t.parent_task || "__root__"; (byParent[k] = byParent[k] || []).push(t); });
	const t = data.totals || {};
	const varClass = flt(t.variance) < 0 ? "sbi-over" : "sbi-under";

	let html = `<style>
		.sbi-stages{border:1px solid var(--border-color);border-radius:4px;overflow:hidden}
		.sbi-stages-head{display:flex;gap:18px;align-items:baseline;padding:10px 14px;background:var(--fg-color);border-bottom:1px solid var(--border-color)}
		.sbi-stages-head b{font-size:13px}.sbi-stages-head span{font-size:12px;color:var(--text-muted)}
		.sbi-row{display:flex;align-items:center;gap:10px;padding:9px 14px;border-bottom:1px solid var(--border-color);font-size:13px}
		.sbi-row:last-child{border-bottom:0}.sbi-row.sbi-child{background:var(--subtle-fg);padding-left:40px}
		.sbi-name{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
		.sbi-name a{color:var(--text-color);font-weight:600;cursor:pointer}.sbi-row.sbi-child .sbi-name a{font-weight:400}
		.sbi-meta{font-size:11px;color:var(--text-muted);font-weight:400}
		.sbi-bar{width:74px;height:6px;background:var(--border-color);border-radius:3px;overflow:hidden;flex:0 0 auto}
		.sbi-bar i{display:block;height:100%;background:var(--text-color)}
		.sbi-pct{width:38px;text-align:right;font-variant-numeric:tabular-nums;font-size:12px;color:var(--text-muted);flex:0 0 auto}
		.sbi-money{width:112px;text-align:right;font-variant-numeric:tabular-nums;flex:0 0 auto}
		.sbi-over{color:#be1e2d}.sbi-under{color:#0f6b3f}.sbi-logs{flex:0 0 auto}
		.sbi-foot{display:flex;gap:8px;padding:10px 14px;background:var(--fg-color);border-top:1px solid var(--border-color)}
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
		const due = task.exp_end_date ? frappe.datetime.str_to_user(task.exp_end_date) : "";
		const meta = [task.status, due].filter(Boolean).join(" Â· ");
		return `<div class="sbi-row ${isChild ? "sbi-child" : ""}">
			<span class="sbi-name">
				<a class="sbi-open-task" data-task="${task.name}">${frappe.utils.escape_html(task.subject || task.name)}</a>
				<span class="sbi-meta">&nbsp;${frappe.utils.escape_html(meta)}</span>
			</span>
			<span class="sbi-bar"><i style="width:${Math.min(pct, 100)}%"></i></span>
			<span class="sbi-pct">${pct}%</span>
			<span class="sbi-money">${sbi_money(task.budget)}</span>
			<span class="sbi-money ${vClass}">${sbi_money(task.actual)}</span>
			<span class="sbi-logs"><button class="btn btn-xs btn-default sbi-add-log" data-task="${task.name}">
				+ Log${task.log_count ? " (" + task.log_count + ")" : ""}</button></span>
		</div>`;
	};
	(byParent["__root__"] || []).forEach((stage) => {
		html += row(stage, false);
		(byParent[stage.name] || []).forEach((child) => { html += row(child, true); });
	});
	html += `<div class="sbi-foot">
		<button class="btn btn-xs btn-default sbi-refresh-stages">Refresh</button>
		<button class="btn btn-xs btn-default sbi-open-tasks">Open task tree</button>
	</div></div>`;
	return html;
}

function sbi_bind_stage_actions($w, frm) {
	$w.find(".sbi-refresh-stages").on("click", () => sbi_render_stage_tree(frm));
	$w.find(".sbi-open-tasks").on("click", () => frappe.set_route("Tree", "Task", { project: frm.doc.name }));

	// open the task in a NEW browser tab
	$w.find(".sbi-open-task").on("click", function () {
		const task = $(this).attr("data-task");
		window.open("/app/task/" + encodeURIComponent(task), "_blank");
	});

	// open a new Daily Work Log in a NEW tab, prefilled for this task
	$w.find(".sbi-add-log").on("click", function () {
		const task = $(this).attr("data-task");
		const route = "/app/daily-work-log/new?project=" +
			encodeURIComponent(frm.doc.name) + "&task=" + encodeURIComponent(task) +
			"&log_date=" + frappe.datetime.get_today();
		window.open(route, "_blank");
	});
}

// ---------------------------------------------------------------------------
// Owner budget panel: set planned amount per account, in one place.
// ---------------------------------------------------------------------------

function sbi_render_budget_panel(frm) {
	const wrapper = frm.get_field("sbi_budget_html");
	if (!wrapper || !wrapper.$wrapper) return;
	wrapper.$wrapper.html('<div class="text-muted" style="padding:12px">Loading budgetâ€¦</div>');

	frappe.call({
		method: "sbi_projects.sbi_projects.stage_tree.get_project_budget",
		args: { project: frm.doc.name },
		callback(r) {
			const data = (r && r.message) || { rows: [], net: 0 };
			wrapper.$wrapper.html(sbi_budget_html(data));
			sbi_bind_budget(wrapper.$wrapper, frm);
		},
		error() { wrapper.$wrapper.html('<div class="text-muted" style="padding:12px">Budget could not be loaded.</div>'); },
	});
}

function sbi_budget_html(data) {
	const rows = data.rows || [];
	const allocated = rows.reduce((s, r) => s + flt(r.budget_amount), 0);
	const net = flt(data.net);
	const left = net - allocated;

	let body = rows.map((r) => `
		<div class="sbi-brow" style="display:flex;align-items:center;gap:10px;padding:7px 14px;border-bottom:1px solid var(--border-color)">
			<span style="flex:1">${frappe.utils.escape_html(r.account_name || r.account)}</span>
			<input class="sbi-bamt form-control input-xs" data-account="${frappe.utils.escape_html(r.account)}"
				style="width:150px;text-align:right" type="number" value="${flt(r.budget_amount)}">
		</div>`).join("");

	if (!rows.length) {
		body = '<div class="text-muted" style="padding:12px">No budget accounts yet. Set them from a sales order or add below.</div>';
	}

	return `<div style="border:1px solid var(--border-color);border-radius:4px;overflow:hidden">
		<div style="display:flex;gap:18px;padding:10px 14px;background:var(--fg-color);border-bottom:1px solid var(--border-color);font-size:12px">
			<span>Contract net <b>${sbi_money(net)}</b></span>
			<span>Allocated <b>${sbi_money(allocated)}</b></span>
			<span style="color:${left < 0 ? '#be1e2d' : 'var(--text-muted)'}">Unallocated <b>${sbi_money(left)}</b></span>
		</div>
		${body}
		<div style="padding:10px 14px;background:var(--fg-color);border-top:1px solid var(--border-color)">
			<button class="btn btn-xs btn-primary sbi-save-budget">Save budget</button>
			<button class="btn btn-xs btn-default sbi-refresh-budget" style="margin-left:6px">Refresh</button>
			<button class="btn btn-xs btn-default sbi-add-account" style="margin-left:6px">+ Add cost head</button>
		</div>
	</div>`;
}

function sbi_bind_budget($w, frm) {
	$w.find(".sbi-refresh-budget").on("click", () => sbi_render_budget_panel(frm));
	$w.find(".sbi-add-account").on("click", function () {
		const d = new frappe.ui.Dialog({
			title: "Add a cost head",
			fields: [
				{ fieldname: "category_name", fieldtype: "Data", label: "Cost head name", reqd: 1,
				  description: "For example: Fuel Cost, Crane Charges, Site Security" },
				{ fieldname: "amount", fieldtype: "Currency", label: "Budget amount" },
			],
			primary_action_label: "Add",
			primary_action(v) {
				frappe.call({
					method: "sbi_projects.sbi_projects.stage_tree.add_budget_account",
					args: { project: frm.doc.name, category_name: v.category_name, amount: v.amount || 0 },
					freeze: true,
					callback() {
						d.hide();
						frappe.show_alert({ message: "Cost head added", indicator: "green" });
						sbi_render_budget_panel(frm);
					},
				});
			},
		});
		d.show();
	});

	$w.find(".sbi-save-budget").on("click", function () {
		const updates = [];
		$w.find(".sbi-bamt").each(function () {
			updates.push({ account: $(this).attr("data-account"), amount: flt($(this).val()) });
		});
		frappe.call({
			method: "sbi_projects.sbi_projects.stage_tree.save_project_budget",
			args: { project: frm.doc.name, updates: JSON.stringify(updates) },
			freeze: true, freeze_message: "Saving budgetâ€¦",
			callback() { frappe.show_alert({ message: "Budget saved", indicator: "green" }); sbi_render_budget_panel(frm); },
		});
	});
}
