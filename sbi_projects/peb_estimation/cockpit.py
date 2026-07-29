# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""
The Sales Order cockpit.

Everything about a job -- the project, the payment stages, the BOQ, what has
been requested, ordered, billed and spent -- gathered onto the Sales Order so
the owner can see the whole picture without opening eight other lists.

Each block is fetched independently and defensively: a doctype that isn't
installed, or a field that doesn't exist on this site, quietly yields an empty
block instead of breaking the panel.

Financial figures are restricted -- see `can_view()`.
"""

import frappe
from frappe import _
from frappe.utils import flt

# Roles allowed to see the money view. Site staff and project engineers see
# nothing from this panel (the Q3 principle applied to the Sales Order).
COCKPIT_ROLES = ("System Manager", "Sales Manager")


def can_view():
	roles = set(frappe.get_roles())
	return bool(roles.intersection(COCKPIT_ROLES))


@frappe.whitelist()
def get_cockpit(sales_order):
	"""Return every cockpit block for one Sales Order."""
	if not can_view():
		return {"allowed": False}

	if not frappe.db.exists("Sales Order", sales_order):
		frappe.throw(_("Sales Order not found."))

	so = frappe.get_doc("Sales Order", sales_order)

	return {
		"allowed": True,
		"order": {
			"name": so.name,
			"customer": so.customer_name or so.customer,
			"total": flt(so.grand_total),
			"status": so.status,
			"currency": so.currency,
		},
		"project": _project(so),
		"boq": _boq(so),
		"stages": _stages(so),
		"procurement": _procurement(so),
		"billing": _billing(so),
		"cost": _cost(so),
	}


# --------------------------------------------------------------------------- #
# blocks
# --------------------------------------------------------------------------- #
def _project(so):
	if not so.get("project"):
		return {}
	try:
		p = frappe.db.get_value(
			"Project", so.project,
			["name", "project_name", "status", "percent_complete", "expected_end_date"],
			as_dict=True,
		)
		return dict(p or {})
	except Exception:
		return {}


def _boq(so):
	boq = so.get("sbi_estimation_boq")
	if not boq:
		return {}
	try:
		d = frappe.db.get_value(
			"Estimation Sheet BOQ", boq,
			["name", "base_total", "grand_total", "status", "boq_type"],
			as_dict=True,
		) or {}
		d["lines"] = frappe.db.count("Estimation Sheet BOQ Line", {"parent": boq})
		return dict(d)
	except Exception:
		return {}


def _stages(so):
	"""Payment terms are the stages. Billed status comes from milestone billing."""
	try:
		fields = ["idx", "payment_term", "description", "invoice_portion",
		          "payment_amount", "due_date"]
		meta = frappe.get_meta("Payment Schedule")
		# sbi_projects adds these: the stage label and the milestone-billing flags
		for extra in ("project_stage", "sbi_billed", "sbi_sales_invoice"):
			if meta.has_field(extra):
				fields.append(extra)

		rows = frappe.get_all(
			"Payment Schedule",
			filters={"parent": so.name, "parenttype": "Sales Order"},
			fields=fields,
			order_by="idx asc",
		)
		billed_rows = [r for r in rows if r.get("sbi_billed")]
		billed = sum(flt(r.get("payment_amount")) for r in billed_rows)
		total = sum(flt(r.get("payment_amount")) for r in rows)
		return {
			"rows": rows,
			"billed_amount": billed,
			"total_amount": total,
			"stages_done": len(billed_rows),
			"stages_total": len(rows),
			"value_percent": (billed / total * 100) if total else 0,
		}
	except Exception:
		return {"rows": [], "billed_amount": 0, "total_amount": 0,
		        "stages_done": 0, "stages_total": 0, "value_percent": 0}


def _procurement(so):
	"""Material Requests and Purchase Orders raised against this order."""
	out = {"material_requests": [], "purchase_orders": []}

	try:
		mr = frappe.get_all(
			"Material Request Item",
			filters={"sales_order": so.name, "docstatus": ["<", 2]},
			fields=["parent"],
			group_by="parent",
		)
		names = [r.parent for r in mr]
		if names:
			out["material_requests"] = frappe.get_all(
				"Material Request",
				filters={"name": ["in", names]},
				fields=["name", "status", "transaction_date", "per_ordered"],
				order_by="transaction_date desc",
				limit=20,
			)
	except Exception:
		pass

	try:
		po = frappe.get_all(
			"Purchase Order Item",
			filters={"sales_order": so.name, "docstatus": ["<", 2]},
			fields=["parent"],
			group_by="parent",
		)
		names = [r.parent for r in po]
		if names:
			out["purchase_orders"] = frappe.get_all(
				"Purchase Order",
				filters={"name": ["in", names]},
				fields=["name", "status", "transaction_date", "grand_total", "per_received"],
				order_by="transaction_date desc",
				limit=20,
			)
			out["po_value"] = sum(flt(p.grand_total) for p in out["purchase_orders"])
	except Exception:
		pass

	return out


def _billing(so):
	"""Sales Invoices raised against this order."""
	try:
		si = frappe.get_all(
			"Sales Invoice Item",
			filters={"sales_order": so.name, "docstatus": ["<", 2]},
			fields=["parent"],
			group_by="parent",
		)
		names = [r.parent for r in si]
		if not names:
			return {"invoices": [], "invoiced": 0, "outstanding": 0}

		invoices = frappe.get_all(
			"Sales Invoice",
			filters={"name": ["in", names]},
			fields=["name", "status", "posting_date", "grand_total", "outstanding_amount"],
			order_by="posting_date desc",
			limit=20,
		)
		return {
			"invoices": invoices,
			"invoiced": sum(flt(i.grand_total) for i in invoices if i.status != "Cancelled"),
			"outstanding": sum(flt(i.outstanding_amount) for i in invoices),
		}
	except Exception:
		return {"invoices": [], "invoiced": 0, "outstanding": 0}


def _cost(so):
	"""Actual spend booked against the project, split by cost centre.

	sbi_projects gives every site a cost-centre group with category leaves
	(Material, Manpower, Equipment, Subcontracting and so on), so grouping GL
	entries by cost centre is the category breakdown.
	"""
	if not so.get("project"):
		return {"rows": [], "total": 0}

	try:
		rows = frappe.db.sql(
			"""
			select cost_center, sum(debit) - sum(credit) as amount
			from `tabGL Entry`
			where project = %s and is_cancelled = 0
			group by cost_center
			having amount <> 0
			order by amount desc
			""",
			(so.project,),
			as_dict=True,
		)
		return {
			"rows": rows,
			"total": sum(flt(r.amount) for r in rows),
		}
	except Exception:
		return {"rows": [], "total": 0}
