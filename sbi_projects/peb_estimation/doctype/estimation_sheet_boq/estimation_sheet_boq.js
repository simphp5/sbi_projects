// Copyright (c) 2026, Velmaska and contributors
// For license information, please see license.txt

frappe.ui.form.on("Estimation Sheet BOQ", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("Recalculate Rates (WA)"), () => {
			frm.call({
				doc: frm.doc,
				method: "recalculate_rates",
				freeze: true,
				freeze_message: __("Recalculating from Rate Card..."),
				callback(r) {
					frm.reload_doc();
					frappe.show_alert({
						message: __("{0} line(s) updated. Manual lines were left untouched.", [r.message || 0]),
						indicator: "green",
					});
				},
			});
		}).addClass("btn-primary");



		// ---- quotation ----
		if (frm.doc.quotation) {
			frm.add_custom_button(__("View Quotation"), () => {
				frappe.set_route("Form", "Quotation", frm.doc.quotation);
			}).addClass("btn-primary");
		} else if ((frm.doc.lines || []).length) {
			frm.add_custom_button(__("Create Quotation"), () => frm.trigger("create_quotation"))
				.addClass("btn-primary");
		}

		// ---- stages ----
		frm.add_custom_button(__("Load Stages"), () => frm.trigger("load_stages"), __("Stages"));

		frm.trigger("apply_stage_options");

		// ---- BOQ line import ----
		frm.add_custom_button(__("Download Template"), () => {
			window.open(
				"/api/method/sbi_projects.peb_estimation.doctype.estimation_sheet_boq"
				+ ".estimation_sheet_boq.download_boq_template"
			);
		}, __("BOQ Lines"));

		frm.add_custom_button(__("Upload Lines"), () => {
			frm.trigger("upload_lines");
		}, __("BOQ Lines"));

		// stage-wise subtotal hint
		const byStage = {};
		(frm.doc.lines || []).forEach((l) => {
			const s = l.stage || __("Unassigned");
			byStage[s] = (byStage[s] || 0) + (l.amount || 0);
		});
		const stages = Object.keys(byStage);
		if (stages.length > 1) {
			frm.dashboard.add_comment(
				__("Stages: ") + stages.map((s) => s + " " + format_currency(byStage[s], frm.doc.currency)).join("  ·  "),
				"blue", true
			);
		}
	},

	create_quotation(frm) {
		const d = new frappe.ui.Dialog({
			title: __("Create Quotation"),
			fields: [
				{
					fieldname: "group_by",
					label: __("Show on quotation as"),
					fieldtype: "Select",
					options: ["Line", "Category", "Stage"].join("\n"),
					default: "Line",
					reqd: 1,
					description: __("Line keeps every BOQ row. Category or Stage rolls them into lump sums."),
				},
				{
					fieldname: "valid_days",
					label: __("Valid for (days)"),
					fieldtype: "Int",
					default: 30,
					reqd: 1,
				},
				{
					fieldname: "note",
					fieldtype: "HTML",
					options:
						"<p class='text-muted small'>Markup is folded into the selling rates, "
						+ "so the quotation carries clean prices and no internal build-up.</p>",
				},
			],
			primary_action_label: __("Create"),
			primary_action(values) {
				frm.call({
					doc: frm.doc,
					method: "create_quotation",
					args: { group_by: values.group_by, valid_days: values.valid_days },
					freeze: true,
					freeze_message: __("Creating quotation..."),
					callback(r) {
						d.hide();
						const m = r.message || {};
						frappe.show_alert({
							message: __("{0} created ({1} row(s), {2}).", [
								m.quotation, m.rows, format_currency(m.total, frm.doc.currency),
							]),
							indicator: "green",
						});
						if (m.quotation) frappe.set_route("Form", "Quotation", m.quotation);
					},
				});
			},
		});
		d.show();
	},

	load_stages(frm) {
		const has_so = !!frm.doc.sales_order;
		const d = new frappe.ui.Dialog({
			title: __("Load Stages"),
			fields: [
				{
					fieldname: "source",
					label: __("Load from"),
					fieldtype: "Select",
					options: ["Payment Terms Template", "Sales Order"].join("\n"),
					default: has_so ? "Sales Order" : "Payment Terms Template",
					reqd: 1,
				},
				{
					fieldname: "note",
					fieldtype: "HTML",
					options:
						"<p class='text-muted small'>Stages are the payment terms. "
						+ "Loading them here keeps the BOQ, the quotation and the invoices "
						+ "on the same sequence. You can also type stages in by hand.</p>",
				},
				{
					fieldname: "replace",
					label: __("Replace existing stages"),
					fieldtype: "Check",
					default: 1,
				},
			],
			primary_action_label: __("Load"),
			primary_action(values) {
				frm.call({
					doc: frm.doc,
					method: "load_stages",
					args: { source: values.source, replace: values.replace ? 1 : 0 },
					freeze: true,
					callback(r) {
						d.hide();
						frm.reload_doc();
						frappe.show_alert({
							message: __("{0} stage(s) loaded from {1}.", [
								(r.message || {}).added || 0,
								(r.message || {}).source || "",
							]),
							indicator: "green",
						});
					},
				});
			},
		});
		d.show();
	},

	apply_stage_options(frm) {
		// let the line-level Stage field offer the stages defined on this sheet
		const opts = (frm.doc.stages || []).map((s) => s.stage_name).filter(Boolean);
		const grid = frm.fields_dict.lines && frm.fields_dict.lines.grid;
		if (!grid) return;
		grid.update_docfield_property("stage", "options", opts.join("\n"));
		grid.update_docfield_property(
			"stage",
			"description",
			opts.length
				? __("Choose one of the {0} stage(s) defined above.", [opts.length])
				: __("No stages defined yet - use Stages > Load Stages, or type freely.")
		);
	},

	upload_lines(frm) {
		const d = new frappe.ui.Dialog({
			title: __("Upload BOQ Lines"),
			fields: [
				{
					fieldname: "info",
					fieldtype: "HTML",
					options:
						"<p class='text-muted small'>Use the downloaded template. "
						+ "Leave <b>Rate</b> blank to price the line from the Rate Card (WA); "
						+ "fill a Rate to keep it as a Manual price.</p>",
				},
				{
					fieldname: "file",
					label: __("File (.xlsx or .csv)"),
					fieldtype: "Attach",
					reqd: 1,
				},
				{
					fieldname: "replace",
					label: __("Replace existing lines"),
					fieldtype: "Check",
					default: 0,
					description: __("Unticked, the rows are appended to the current lines."),
				},
			],
			primary_action_label: __("Import"),
			primary_action(values) {
				frm.call({
					doc: frm.doc,
					method: "import_lines",
					args: { file_url: values.file, replace: values.replace ? 1 : 0 },
					freeze: true,
					freeze_message: __("Importing lines..."),
					callback(r) {
						d.hide();
						frm.reload_doc();
						const m = r.message || {};
						let msg = __("{0} line(s) imported.", [m.added || 0]);
						if (m.skipped) {
							msg += " " + __("{0} blank row(s) skipped.", [m.skipped]);
						}
						if ((m.unknown || []).length) {
							frappe.msgprint({
								title: __("Imported with warnings"),
								indicator: "orange",
								message:
									msg
									+ "<br><br><b>" + __("Unknown Work Item codes (left blank):") + "</b><br>"
									+ m.unknown.join("<br>"),
							});
						} else {
							frappe.show_alert({ message: msg, indicator: "green" });
						}
					},
				});
			},
		});
		d.show();
	},
});

frappe.ui.form.on("Estimation Sheet BOQ Line", {
	rate(frm, cdt, cdn) {
		// SBI typed a rate manually -> flag as Manual so Recalculate won't overwrite it
		const row = locals[cdt][cdn];
		if (row.rate_source !== "Manual") {
			frappe.model.set_value(cdt, cdn, "rate_source", "Manual");
		}
		frappe.model.set_value(cdt, cdn, "amount", (row.qty || 0) * (row.rate || 0));
	},
	qty(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "amount", (row.qty || 0) * (row.rate || 0));
	},
	work_item(frm, cdt, cdn) {
		// new work item -> pull WA rate unless the row is already manual
		const row = locals[cdt][cdn];
		if (!row.work_item || row.rate_source === "Manual") return;
		frappe.call({
			method: "frappe.client.get",
			args: { doctype: "Work Item", name: row.work_item },
			callback() {
				// rate fetch happens on server Recalculate; here we just set category/uom
			},
		});
		frappe.db.get_value("Work Item", row.work_item, ["category", "uom"]).then((r) => {
			if (r && r.message) {
				frappe.model.set_value(cdt, cdn, "category", r.message.category);
				frappe.model.set_value(cdt, cdn, "uom", r.message.uom);
			}
		});
	},
});
