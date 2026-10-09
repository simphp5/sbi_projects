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
		frm.add_custom_button(__("Import Opening Balances"), () => tally.opening(frm), __("Sync"));
		frm.add_custom_button(__("Load Default Group Map"), () => tally.call(frm, "load_default_group_map",
			null, true), __("Sync"));
		frm.add_custom_button(__("Sync Log"), () => frappe.set_route("List", "Tally Sync Log"));

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
				${a.last_error ? `<div class="text-danger small" style="line-height:1.4;margin-top:6px">${esc(a.last_error)}</div>` : ""}
				${a.user ? "" : `<div class="small" style="margin-top:6px">${__("Step 1: click <b>Agent > Generate Agent Key</b>, then install the agent on the Tally computer.")}</div>`}
			</div>`;
			frm.get_field("agent_status_html").$wrapper.html(status);

			const cols = ["Exported", "Imported", "Linked", "Failed", "Deleted"];
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
				<div class="text-muted small">${__("Exported = ERPNext to Tally. Imported = Tally to ERPNext. Linked = already existed on both sides and was matched by name.")}
				${a.last_sync_on ? " " + __("Last complete sync: {0}", [frappe.datetime.str_to_user(a.last_sync_on)]) : ""}</div>`;
			frm.get_field("summary_html").$wrapper.html(html);
		});
	},

	filter(col) {
		return {
			Exported: "&direction=Export&status=Success",
			Imported: "&direction=Import&status=Success",
			Linked: "&status=Linked",
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
