// Copyright (c) 2026, Velmaska and contributors
const TALLY_API = "sbi_projects.tally.admin.";
const AGENT_FILES = "/assets/sbi_projects/tally_agent/";

frappe.ui.form.on("Tally Settings", {
	setup(frm) {
		frm.set_query("erpnext_account", "group_map", () => ({
			filters: { company: frm.doc.company, is_group: 1 },
		}));
		frm.set_query("default_cost_center", () => ({
			filters: { company: frm.doc.company, is_group: 0 },
		}));
	},

	sync_direction(frm) {
		frm.refresh();
	},

	refresh(frm) {
		tally.render_summary(frm);

		frm.add_custom_button(__("Generate Agent Key"), () => tally.generate_key(frm), __("Agent"));
		frm.add_custom_button(__("Download Agent"), () => window.open(AGENT_FILES + "tally_agent.py"), __("Agent"));
		frm.add_custom_button(__("Download Auto-start Installer"),
			() => window.open(AGENT_FILES + "agent_autostart.ps1"), __("Agent"));

		frm.add_custom_button(__("Retry Failed"), () => tally.call(frm, "retry_failed",
			__("Failed records will be tried again on the next sync.")), __("Sync"));
		frm.add_custom_button(__("Re-read Tally Masters"), () => tally.call(frm, "resync_masters",
			__("Ledgers and stock items will be read again from Tally on the next sync.")), __("Sync"));
		frm.add_custom_button(__("Re-check Tally Vouchers"), () => tally.call(frm, "reimport_vouchers",
			__("All Tally vouchers since the Sync From Date will be compared again on the next sync. Nothing already imported is duplicated.")), __("Sync"));
		if (frm.doc.sync_direction !== "ERPNext to Tally only") {
			frm.add_custom_button(__("Import Opening Balances"), () => tally.opening(frm), __("Sync"));
		}
		frm.add_custom_button(__("Repair Customer / Supplier Ledgers"), () => tally.repair(frm), __("Sync"));
		frm.add_custom_button(__("Remove Duplicate Tally Entries"), () => tally.dedupe(frm), __("Sync"));
		frm.add_custom_button(__("Remove Tally Data from a Company"), () => tally.remove_company(frm), __("Sync"));
		frm.add_custom_button(__("Load Default Group Map"), () => tally.call(frm, "load_default_group_map",
			null, true), __("Sync"));
		frm.add_custom_button(__("Sync Log"), () => frappe.set_route("List", "Tally Sync Log"));
		frm.add_custom_button(__("Dashboard"), () => frappe.set_route("tally-dashboard"));

		if (frm._tally_timer) clearInterval(frm._tally_timer);
		frm._tally_timer = setInterval(() => {
			if (frappe.get_route_str() === "Form/Tally Settings") tally.render_summary(frm);
			else clearInterval(frm._tally_timer);
		}, 30000);
	},
});

const tally = {
	call(frm, method, message, reload) {
		frappe.call({ method: TALLY_API + method, freeze: true }).then((r) => {
			if (message) frappe.show_alert({ message, indicator: "green" }, 6);
			if (method === "retry_failed" && r.message) {
				frappe.show_alert({ message: __("{0} ERPNext vouchers queued again", [r.message.vouchers]), indicator: "blue" });
			}
			if (method === "load_default_group_map") {
				frappe.show_alert({ message: __("{0} group rows added", [r.message]), indicator: "green" });
			}
			if (reload) frm.reload_doc(); else tally.render_summary(frm);
		});
	},

	generate_key(frm) {
		if (frm.is_dirty()) {
			frappe.msgprint(__("Save the settings first."));
			return;
		}
		frappe.confirm(
			__("This creates the agent user (if needed) and a NEW secret. An agent already running with the old key will stop until you give it the new config.json. Continue?"),
			() => frappe.call({ method: TALLY_API + "generate_agent_key", freeze: true }).then((r) => {
				const blob = new Blob([JSON.stringify(r.message, null, 2)], { type: "application/json" });
				const a = document.createElement("a");
				a.href = URL.createObjectURL(blob);
				a.download = "config.json";
				document.body.appendChild(a);
				a.click();
				a.remove();
				frappe.msgprint({
					title: __("Agent key created"),
					indicator: "green",
					message: __("<b>config.json</b> has been downloaded. Put it in the same folder as <b>tally_agent.py</b> on the Tally computer. This secret is not shown again; generate a new key if the file is lost."),
				});
				frm.reload_doc();
			})
		);
	},

	repair(frm) {
		const call = (dry_run) => frappe.call({
			method: TALLY_API + "repair_party_ledgers", args: { dry_run }, freeze: true,
			freeze_message: dry_run ? __("Checking...") : __("Repairing..."),
		});
		call(1).then((r) => {
			const s = r.message;
			if (!s.wrong_accounts && !s.account_types_to_set) {
				frappe.msgprint(__("Nothing to repair."));
				return;
			}
			let html = `<p>${__("Accounts created from Tally customer / supplier ledgers")}: <b>${s.wrong_accounts}</b></p>
				<p>${__("Will be removed (recreated as Customers / Suppliers on the next sync)")}: <b>${s.will_remove}</b></p>`;
			if (s.sample.length) html += `<p class="small text-muted">${frappe.utils.escape_html(s.sample.join(", "))}...</p>`;
			if (s.tally_journal_entries.length)
				html += `<p>${__("Imported Journal Entries removed and re-imported")}: ${s.tally_journal_entries.join(", ")}</p>`;
			if (s.blocked.length)
				html += `<p class="text-danger">${__("Kept because ERPNext transactions use them")}: ${frappe.utils.escape_html(s.blocked.join("; "))}</p>`;
			if (s.account_types_to_set)
				html += `<p>${__("Bank / Cash / Tax account types to fill in")}: <b>${s.account_types_to_set}</b></p>`;
			frappe.confirm(html + `<p><b>${__("Go ahead?")}</b></p>`, () => call(0).then(() => {
				frappe.msgprint(__("Repaired. The next sync (within 2 minutes) creates the Customers and Suppliers."));
				frm.reload_doc();
			}));
		});
	},

	remove_company(frm) {
		const d = new frappe.ui.Dialog({
			title: __("Remove Tally Data from a Company"),
			fields: [
				{ fieldname: "company", fieldtype: "Link", options: "Company", label: __("ERPNext Company"), reqd: 1 },
				{ fieldtype: "HTML", options: `<p class="small text-muted">${__("Use this when Tally data went into the wrong ERPNext company. It removes the Journal Entries imported from Tally and the Accounts the sync created in that company. Customers and Suppliers are kept. Every Tally company is then read again into the company set in the Tally Companies table.")}</p>` },
			],
			primary_action_label: __("Preview"),
			primary_action(values) {
				d.hide();
				const call = (dry_run) => frappe.call({ method: TALLY_API + "remove_company_tally_data",
					args: { company: values.company, dry_run }, freeze: true });
				call(1).then((r) => {
					const s = r.message;
					const esc = frappe.utils.escape_html;
					let html = `<p><b>${esc(s.company)}</b></p>
						<p>${__("Journal Entries from Tally to remove")}: <b>${s.journal_entries}</b> (${format_currency(s.amount, "INR", 0)})</p>
						<p>${__("Accounts created by the sync to remove")}: <b>${s.accounts_removed}</b></p>
						<p>${__("Accounts only unlinked from Tally (kept)")}: <b>${s.accounts_unlinked}</b></p>`;
					if (s.sample.length) html += `<p class="small text-muted">${esc(s.sample.join(", "))}...</p>`;
					if (s.blocked.length) html += `<p class="text-danger small">${__("Kept, used by other transactions")}: ${esc(s.blocked.join("; "))}</p>`;
					if (!s.journal_entries && !s.accounts_removed && !s.accounts_unlinked) {
						frappe.msgprint(__("No Tally data found in this company."));
						return;
					}
					frappe.confirm(html + `<p><b>${__("This cannot be undone. Go ahead?")}</b></p>`, () => call(0).then(() => {
						frappe.msgprint(__("Removed. The next sync reads every Tally company again."));
						frm.reload_doc();
					}));
				});
			},
		});
		d.show();
	},

	dedupe(frm) {
		const call = (dry_run) => frappe.call({
			method: TALLY_API + "remove_duplicate_tally_jes", args: { dry_run }, freeze: true });
		call(1).then((r) => {
			const s = r.message;
			if (!s.extra_entries) {
				frappe.msgprint(__("No duplicate Tally entries found."));
				return;
			}
			const html = `<p>${__("Tally vouchers booked more than once")}: <b>${s.vouchers}</b></p>
				<p>${__("Extra Journal Entries to cancel and remove")}: <b>${s.extra_entries}</b>
				(${format_currency(s.amount, "INR", 0)})</p>
				<p class="small text-muted">${frappe.utils.escape_html(s.sample.join("; "))}</p>
				<p>${__("The first Journal Entry of each voucher is kept.")}</p><p><b>${__("Go ahead?")}</b></p>`;
			frappe.confirm(html, () => call(0).then(() => {
				frappe.msgprint(__("Duplicates removed."));
				frm.reload_doc();
			}));
		});
	},

	opening(frm) {
		const d = new frappe.ui.Dialog({
			title: __("Import Opening Balances from Tally"),
			fields: [
				{ fieldname: "opening_date", fieldtype: "Date", label: __("Opening Entry Date"), reqd: 1,
					default: frm.doc.opening_date || frm.doc.start_date },
				{ fieldtype: "HTML", options: "<p class='text-muted small'>" +
					__("On the next sync the agent reads every Tally ledger's opening balance. ERPNext creates ONE draft Opening Journal Entry (balancing difference to Temporary Opening). Income/expense and stock ledgers are left out. Review it before submitting.") + "</p>" },
			],
			primary_action_label: __("Request"),
			primary_action(values) {
				d.hide();
				frappe.call({ method: TALLY_API + "request_opening", args: values }).then(() => frm.reload_doc());
			},
		});
		d.show();
	},

	render_summary(frm) {
		frappe.call({ method: TALLY_API + "get_summary" }).then((r) => {
			const s = r.message || {};
			const a = s.agent || {};
			const esc = frappe.utils.escape_html;
			const ago = a.seconds_ago == null ? __("never")
				: a.seconds_ago < 90 ? __("{0} s ago", [Math.round(a.seconds_ago)])
				: a.seconds_ago < 5400 ? __("{0} min ago", [Math.round(a.seconds_ago / 60)])
				: __("{0} h ago", [Math.round(a.seconds_ago / 3600)]);
			const dot = (ok, yes, no) =>
				`<span class="indicator-pill ${ok ? "green" : "red"}">${ok ? yes : no}</span>`;

			let status = `<div style="line-height:2">
				${dot(a.online, __("Agent online"), __("Agent offline"))} <span class="text-muted">${__("last seen")} ${ago}</span><br>
				${dot(a.tally_reachable, __("Tally company open"), __("Tally not ready"))}
				${a.enabled ? "" : `<span class="indicator-pill orange">${__("Sync disabled")}</span>`}
				<span class="indicator-pill blue">${esc(frm.doc.sync_direction || "Tally to ERPNext only")}</span>
				${(s.companies || []).map((c) => `<div class="small" style="line-height:1.6">
					<span class="indicator ${c.ready ? "green" : "red"}"></span>
					${esc(c.tally_company)} → ${esc(c.company)} ${c.ready ? "" : `<span class="text-danger">(${esc(c.error || __("not open in Tally"))})</span>`}</div>`).join("")}
				${a.last_error ? `<div class="text-danger small" style="line-height:1.4;margin-top:6px">${esc(a.last_error)}</div>` : ""}
				${a.user ? "" : `<div class="small" style="margin-top:6px">${__("Step 1: click <b>Agent > Generate Agent Key</b>, then install the agent on the Tally computer.")}</div>`}
			</div>`;
			frm.get_field("agent_status_html").$wrapper.html(status);

			const cols = ["Exported", "Imported", "Linked", "Skipped", "Failed", "Deleted"];
			const types = ["Voucher", "Ledger", "Party", "Stock Item", "Opening Balance"];
			const table = s.table || {};
			const total = {};
			let body = "";
			types.forEach((t) => {
				const row = table[t] || {};
				body += `<tr><td>${__(t)}</td>` + cols.map((c) => {
					total[c] = (total[c] || 0) + (row[c] || 0);
					const val = row[c] || 0;
					const cls = c === "Failed" && val ? "text-danger" : "";
					return `<td class="text-right ${cls}"><a href="/app/tally-sync-log?record_type=${encodeURIComponent(t)}${tally.filter(c)}">${val}</a></td>`;
				}).join("") + "</tr>";
			});
			const today = s.today || {};
			const html = `
				<div class="row" style="margin-bottom:12px">
					${tally.tile(__("Waiting to go to Tally"), s.pending_export || 0, "blue")}
					${tally.tile(__("Sent to Tally today"), today.Export || 0, "green")}
					${tally.tile(__("Received from Tally today"), today.Import || 0, "green")}
					${tally.tile(__("Failed (all time)"), total.Failed || 0, total.Failed ? "red" : "gray")}
				</div>
				<table class="table table-bordered table-sm" style="max-width:720px">
					<thead><tr><th>${__("Record")}</th>${cols.map((c) => `<th class="text-right">${__(c)}</th>`).join("")}</tr></thead>
					<tbody>${body}</tbody>
					<tfoot><tr><th>${__("Total")}</th>${cols.map((c) => `<th class="text-right">${total[c] || 0}</th>`).join("")}</tr></tfoot>
				</table>
				<div class="text-muted small">${__("Exported = ERPNext to Tally. Imported = Tally to ERPNext. Linked = already existed on both sides and was matched by name. Skipped = Tally voucher already entered in ERPNext, not imported again.")}
				${a.last_sync_on ? " " + __("Last complete sync: {0}", [frappe.datetime.str_to_user(a.last_sync_on)]) : ""}</div>`;
			frm.get_field("summary_html").$wrapper.html(html);
		});
	},

	filter(col) {
		return {
			Exported: "&direction=Export&status=Success",
			Imported: "&direction=Import&status=Success",
			Linked: "&status=Linked",
			Skipped: "&status=Skipped",
			Failed: "&status=Failed",
			Deleted: "&status=Deleted",
		}[col];
	},

	tile(label, value, colour) {
		return `<div class="col-sm-3"><div style="border:1px solid var(--border-color);border-radius:8px;padding:10px 14px">
			<div class="text-muted small">${label}</div>
			<div style="font-size:22px;font-weight:600;color:var(--${colour}-600, inherit)">${value}</div></div></div>`;
	},
};
