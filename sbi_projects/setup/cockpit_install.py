# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""
Installs the Sales Order cockpit panel.

Delivered as a seeded Client Script rather than a bundled .js file so it does
not collide with the existing sales_order.js, and needs no hooks.py change.
The script is rewritten on every migrate, so edits belong here, not in the UI.
"""

import frappe

FIELDNAME = "sbi_cockpit"
SCRIPT_NAME = "SBI Sales Order Cockpit"

CLIENT_SCRIPT = r"""
frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.trigger("sbi_render_cockpit");
	},

	sbi_render_cockpit(frm) {
		const wrapper = frm.get_field("sbi_cockpit");
		if (!wrapper || !wrapper.$wrapper) return;

		frappe.call({
			method: "sbi_projects.peb_estimation.cockpit.get_cockpit",
			args: { sales_order: frm.doc.name },
			callback(r) {
				const d = r.message || {};
				if (!d.allowed) {
					wrapper.$wrapper.html("");
					return;
				}
				wrapper.$wrapper.html(sbi_cockpit_html(d, frm));
			},
		});
	},
});

function sbi_money(v, cur) {
	return format_currency(v || 0, cur);
}

function sbi_link(dt, dn, label) {
	if (!dn) return "-";
	const url = "/app/" + frappe.router.slug(dt) + "/" + encodeURIComponent(dn);
	return `<a href="${url}">${frappe.utils.escape_html(label || dn)}</a>`;
}

function sbi_card(title, bodyHtml, footHtml) {
	return `
	<div style="flex:1 1 300px;border:1px solid var(--border-color);border-radius:8px;
	            padding:12px 14px;background:var(--card-bg);min-width:280px">
		<div style="font-size:11px;text-transform:uppercase;letter-spacing:.5px;
		            color:var(--text-muted);font-weight:600;margin-bottom:8px">${title}</div>
		<div style="font-size:13px">${bodyHtml}</div>
		${footHtml ? `<div style="margin-top:8px;padding-top:8px;
			border-top:1px solid var(--border-color);font-size:12px;
			color:var(--text-muted)">${footHtml}</div>` : ""}
	</div>`;
}

function sbi_cockpit_html(d, frm) {
	const cur = (d.order || {}).currency;
	const cards = [];

	// --- project ---
	const p = d.project || {};
	cards.push(sbi_card(__("Project"),
		p.name
			? `<div style="font-weight:600;margin-bottom:4px">${sbi_link("Project", p.name, p.project_name || p.name)}</div>
			   <div>${__("Status")}: ${frappe.utils.escape_html(p.status || "-")}</div>
			   <div>${__("Complete")}: <b>${Math.round(p.percent_complete || 0)}%</b></div>`
			: `<span class="text-muted">${__("No project yet — use Create ▸ Project (with Stages)")}</span>`
	));

	// --- progress ---
	const stg = d.stages || {};
	const donePct = stg.stages_total
		? Math.round((stg.stages_done / stg.stages_total) * 100) : 0;
	const workPct = Math.round((p.percent_complete || 0));
	const bar = (label, val, colour) => `
		<div style="margin-bottom:8px">
			<div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px">
				<span>${label}</span><span><b>${val}%</b></span>
			</div>
			<div style="height:6px;background:var(--gray-200);border-radius:3px;overflow:hidden">
				<div style="height:100%;width:${Math.min(val,100)}%;background:${colour}"></div>
			</div>
		</div>`;
	cards.push(sbi_card(__("Progress"),
		bar(__("Stages billed"), donePct, "var(--blue-500)")
		+ bar(__("Work complete"), workPct, "var(--green-500)"),
		stg.stages_total
			? __("{0} of {1} stages billed", [stg.stages_done, stg.stages_total]) : ""
	));

	// --- BOQ ---
	const b = d.boq || {};
	cards.push(sbi_card(__("Estimation BOQ"),
		b.name
			? `<div style="font-weight:600;margin-bottom:4px">${sbi_link("Estimation Sheet BOQ", b.name)}</div>
			   <div>${__("Lines")}: ${b.lines || 0}</div>
			   <div>${__("Value")}: <b>${sbi_money(b.grand_total, cur)}</b></div>`
			: `<span class="text-muted">${__("Not linked to a BOQ")}</span>`
	));

	// --- stages / payment terms ---
	const st = d.stages || {};
	const rows = st.rows || [];
	let stageHtml = `<span class="text-muted">${__("No payment terms set")}</span>`;
	if (rows.length) {
		stageHtml = `<table style="width:100%;font-size:12px">` + rows.map((r) => {
			const done = r.sbi_billed ? "✓" : "○";
			const colour = r.sbi_billed ? "var(--green-600)" : "var(--text-muted)";
			const label = r.project_stage || r.payment_term || r.description || "-";
			return `<tr>
				<td style="color:${colour};width:16px">${done}</td>
				<td>${frappe.utils.escape_html(label)}</td>
				<td style="text-align:right;white-space:nowrap">${sbi_money(r.payment_amount, cur)}</td>
			</tr>`;
		}).join("") + `</table>`;
	}
	const pct = Math.round(st.value_percent || 0);
	cards.push(sbi_card(__("Stages / Payment Terms"), stageHtml,
		rows.length ? __("Billed {0} of {1} ({2}%)", [
			sbi_money(st.billed_amount, cur), sbi_money(st.total_amount, cur), pct,
		]) : ""));

	// --- procurement ---
	const pr = d.procurement || {};
	const mrs = pr.material_requests || [];
	const pos = pr.purchase_orders || [];
	let procHtml = "";
	procHtml += `<div>${__("Material Requests")}: <b>${mrs.length}</b>`;
	if (mrs.length) {
		procHtml += " — " + mrs.slice(0, 4).map((m) => sbi_link("Material Request", m.name)).join(", ");
		if (mrs.length > 4) procHtml += ` +${mrs.length - 4}`;
	}
	procHtml += `</div><div style="margin-top:4px">${__("Purchase Orders")}: <b>${pos.length}</b>`;
	if (pos.length) {
		procHtml += " — " + pos.slice(0, 4).map((o) => sbi_link("Purchase Order", o.name)).join(", ");
		if (pos.length > 4) procHtml += ` +${pos.length - 4}`;
	}
	procHtml += `</div>`;
	cards.push(sbi_card(__("Procurement"), procHtml,
		pr.po_value ? __("PO value {0}", [sbi_money(pr.po_value, cur)]) : ""));

	// --- billing ---
	const bl = d.billing || {};
	const invs = bl.invoices || [];
	let billHtml = invs.length
		? invs.slice(0, 5).map((i) =>
			`<div>${sbi_link("Sales Invoice", i.name)}
			 <span style="float:right">${sbi_money(i.grand_total, cur)}</span></div>`).join("")
		: `<span class="text-muted">${__("Not invoiced yet")}</span>`;
	cards.push(sbi_card(__("Sales Invoices"), billHtml,
		invs.length ? __("Invoiced {0} · Outstanding {1}", [
			sbi_money(bl.invoiced, cur), sbi_money(bl.outstanding, cur),
		]) : ""));

	// --- cost ---
	const c = d.cost || {};
	const crows = c.rows || [];
	let costHtml = crows.length
		? `<table style="width:100%;font-size:12px">` + crows.slice(0, 8).map((r) =>
			`<tr><td>${frappe.utils.escape_html((r.cost_center || "-").split(" - ")[0])}</td>
			 <td style="text-align:right;white-space:nowrap">${sbi_money(r.amount, cur)}</td></tr>`).join("")
		  + `</table>`
		: `<span class="text-muted">${__("No cost booked yet")}</span>`;
	let margin = "";
	if (c.total && d.order && d.order.total) {
		const m = d.order.total - c.total;
		const mp = Math.round((m / d.order.total) * 100);
		margin = __("Order {0} · Spent {1} · Left {2} ({3}%)", [
			sbi_money(d.order.total, cur), sbi_money(c.total, cur), sbi_money(m, cur), mp,
		]);
	}
	cards.push(sbi_card(__("Cost by Centre"), costHtml, margin));

	return `
	<div style="margin-top:4px">
		<div style="font-size:12px;color:var(--text-muted);margin-bottom:10px">
			${__("Visible to owners and administrators only.")}
		</div>
		<div style="display:flex;flex-wrap:wrap;gap:12px">${cards.join("")}</div>
	</div>`;
}
"""


def install_cockpit():
	"""Create the HTML field and the client script. Safe to re-run."""
	if not frappe.db.exists("DocType", "Sales Order"):
		return 0

	try:
		_field()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "PEB cockpit: custom fields failed")
		raise

	try:
		_script()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "PEB cockpit: client script failed")
		raise

	frappe.db.commit()
	return 1


def _field():
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(
		{
			"Sales Order": [
				{
					# its own tab, anchored to a field that always exists so the
					# custom field validates on any Sales Order layout
					"fieldname": "sbi_cockpit_tab",
					"label": "Project Cockpit",
					"fieldtype": "Tab Break",
					"insert_after": "terms",
				},
				{
					"fieldname": FIELDNAME,
					"fieldtype": "HTML",
					"insert_after": "sbi_cockpit_tab",
					"read_only": 1,
				},
			]
		},
		update=True,
	)


def _script():
	"""Create or refresh the cockpit Client Script.

	Frappe names Client Scripts itself, so the record is found by what it
	targets rather than by a fixed name -- otherwise every migrate would leave
	behind another copy of the same script.
	"""
	existing = frappe.get_all(
		"Client Script",
		filters={"dt": "Sales Order", "view": "Form", "name": ["like", "%Cockpit%"]},
		pluck="name",
		limit=1,
	)
	if not existing:
		existing = frappe.get_all(
			"Client Script",
			filters={"dt": "Sales Order", "view": "Form"},
			pluck="name",
		)
		existing = [n for n in existing
		            if "sbi_cockpit" in (frappe.db.get_value("Client Script", n, "script") or "")]

	if existing:
		doc = frappe.get_doc("Client Script", existing[0])
		doc.script = CLIENT_SCRIPT
		doc.enabled = 1
		doc.save(ignore_permissions=True)
		return

	doc = frappe.get_doc({
		"doctype": "Client Script",
		"name": SCRIPT_NAME,
		"dt": "Sales Order",
		"view": "Form",
		"enabled": 1,
		"script": CLIENT_SCRIPT,
	})
	doc.insert(ignore_permissions=True)
