# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""Milestone / stage billing.

Create a Sales Invoice for one or more selected Payment Schedule rows of a
submitted Sales Order.

Billing modes
-------------
  "Rate Scaled"        (recommended) keeps the Sales Order item lines - same
                       item, HSN and tax - but scales each RATE down to the
                       selected stage percentage. qty is left untouched so
                       whole-number UOMs never hit a fractional-qty error.
  "Single Service Item" one consolidated service line for the selected amount.
  "Proportional Qty"    legacy: scales qty (can fail on whole-number UOMs).

A linked Project is REQUIRED: the invoice's income and GST post against the
project's site "General" cost centre, so without a project there is no site to
cost to. The dialog blocks creation up front and the server enforces it again.

Status write-back
-----------------
On submit, each source Payment Schedule row records how much was billed, when,
and a status (Fully / Partially Billed). Receipts are handled in
payment_hooks.py when a Payment Entry is allocated to the invoice.
"""

import json

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice


# ---------------------------------------------------------------------------
# Read: payment terms of a Sales Order
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_payment_terms(sales_order):
	"""Return every Payment Schedule row of a submitted Sales Order with its
	billed / received state, for the milestone selection dialog."""

	so = frappe.get_doc("Sales Order", sales_order)
	so.check_permission("read")

	if so.docstatus != 1:
		frappe.throw(_("Sales Order {0} is not submitted").format(sales_order))

	if not so.payment_schedule:
		frappe.throw(
			_("Sales Order {0} has no Payment Schedule. Set a Payment Terms Template first.").format(
				sales_order
			)
		)

	project = _project_for_so(so)

	rows = []
	for row in so.payment_schedule:
		rows.append(
			{
				"row_name": row.name,
				"idx": row.idx,
				"payment_term": row.payment_term or _("Term {0}").format(row.idx),
				"stage": row.get("sbi_stage"),
				"description": row.description,
				"due_date": row.due_date,
				"invoice_portion": flt(row.invoice_portion),
				"payment_amount": flt(row.payment_amount),
				"billed": 1 if row.get("sbi_billed") else 0,
				"status": row.get("sbi_status"),
				"billed_amount": flt(row.get("sbi_billed_amount")),
				"received_amount": flt(row.get("sbi_received_amount")),
				"sales_invoice": row.get("sbi_sales_invoice"),
			}
		)

	return {"rows": rows, "project": project}


# ---------------------------------------------------------------------------
# Write: build the milestone Sales Invoice(s)
# ---------------------------------------------------------------------------


@frappe.whitelist()
def make_milestone_invoice(
	sales_order,
	selected_rows,
	billing_mode="Rate Scaled",
	service_item=None,
	split="combined",
):
	"""Create and SAVE draft Sales Invoice(s) for the selected Payment Schedule
	rows, returning their names so the client can open them in a new tab.

	A Project must be linked to the Sales Order.

	Returns {"invoices": [names]} -- first name is the one to open.
	"""

	if isinstance(selected_rows, str):
		selected_rows = json.loads(selected_rows)

	if not selected_rows:
		frappe.throw(_("Select at least one Payment Term"))

	so = frappe.get_doc("Sales Order", sales_order)
	so.check_permission("read")

	project = _project_for_so(so)
	if not project:
		frappe.throw(
			_(
				"No Project is linked to Sales Order {0}. Create the Project first "
				"(Create > Project with Stages) so the milestone invoice can be "
				"costed to the site."
			).format(so.name),
			title=_("Project Required"),
		)

	selected = _resolve_terms(so, selected_rows)

	invoices = []
	if split == "separate" and len(selected) > 1:
		for term in selected:
			si = _build_invoice(so, [term], billing_mode, service_item, project)
			si.insert(ignore_permissions=True)
			invoices.append(si.name)
	else:
		si = _build_invoice(so, selected, billing_mode, service_item, project)
		si.insert(ignore_permissions=True)
		invoices.append(si.name)

	frappe.db.commit()
	return {"invoices": invoices}


def _build_invoice(so, selected, billing_mode, service_item, project):
	total_portion = flt(sum(flt(t.invoice_portion) for t in selected), 6)
	if total_portion <= 0:
		frappe.throw(_("Selected Payment Terms have zero Invoice Portion"))

	si = make_sales_invoice(so.name)

	if billing_mode == "Single Service Item":
		_apply_service_item(si, so, selected, total_portion, service_item)
	elif billing_mode == "Proportional Qty":
		_apply_proportional_qty(si, so, total_portion)
	else:  # Rate Scaled (default)
		_apply_rate_scaled(si, so, total_portion)

	_apply_payment_schedule(si, selected, total_portion)

	stages = [(t.get("sbi_stage") or t.payment_term or _("Term {0}").format(t.idx)) for t in selected]
	si.sbi_stage = ", ".join([s for s in stages if s])[:140]
	si.sbi_source_sales_order = so.name
	si.sbi_milestone_portion = total_portion
	si.sbi_source_payment_terms = json.dumps([t.name for t in selected])

	# cost center: item + tax -> project General leaf
	_apply_project_cost_center(si, project)

	si.run_method("calculate_taxes_and_totals")
	_stamp_tax_cost_center(si, project)

	return si


def _resolve_terms(so, selected_rows):
	term_map = {d.name: d for d in so.payment_schedule}
	selected = []

	for row_name in selected_rows:
		term = term_map.get(row_name)
		if not term:
			frappe.throw(_("Payment Term row {0} no longer exists on {1}").format(row_name, so.name))
		if term.get("sbi_billed"):
			frappe.throw(
				_("Payment Term {0} is already billed in Sales Invoice {1}").format(
					term.payment_term or term.idx, term.get("sbi_sales_invoice") or ""
				)
			)
		selected.append(term)

	selected.sort(key=lambda t: t.idx)
	return selected


# ---------------------------------------------------------------------------
# Billing modes
# ---------------------------------------------------------------------------


def _apply_rate_scaled(si, so, total_portion):
	"""Keep SO item lines; scale each RATE to the stage percentage."""
	factor = total_portion / 100.0
	so_rate = {d.name: flt(d.rate) for d in so.items}
	rate_prec = frappe.get_precision("Sales Invoice Item", "rate") or 2

	rows = []
	for item in si.items:
		orig_rate = so_rate.get(item.so_detail)
		if orig_rate is None:
			rows.append(item)
			continue
		item.rate = flt(orig_rate * factor, rate_prec)
		item.price_list_rate = 0
		item.margin_rate_or_amount = 0
		item.discount_percentage = 0
		item.discount_amount = 0
		if flt(item.rate) > 0 and flt(item.qty) > 0:
			rows.append(item)

	if not rows:
		frappe.throw(_("Nothing left to bill on this Sales Order"))

	si.set("items", rows)


def _uom_needs_whole_number(uom, _cache={}):
	if not uom:
		return False
	if uom not in _cache:
		_cache[uom] = bool(frappe.get_cached_value("UOM", uom, "must_be_whole_number"))
	return _cache[uom]


def _apply_proportional_qty(si, so, total_portion):
	"""Legacy: scale qty (can fail on whole-number UOMs)."""
	factor = total_portion / 100.0
	so_qty = {d.name: flt(d.qty) for d in so.items}
	precision = frappe.get_precision("Sales Invoice Item", "qty") or 3

	rows = []
	fraction_problems = []

	for item in si.items:
		base_qty = so_qty.get(item.so_detail)
		if base_qty is None:
			rows.append(item)
			continue
		new_qty = flt(base_qty * factor, precision)
		if new_qty <= 0:
			continue
		if _uom_needs_whole_number(item.uom) and new_qty != flt(int(new_qty)):
			fraction_problems.append((item.item_code, base_qty, new_qty, item.uom))
		item.qty = new_qty
		rows.append(item)

	if fraction_problems:
		lines = "".join(
			"<li>{0}: {1} &times; {2}% = <b>{3}</b> {4}</li>".format(
				code, base, flt(total_portion, 2), new, uom
			)
			for code, base, new, uom in fraction_problems
		)
		frappe.throw(
			_("Proportional Qty billing would create fractional quantities, which these items do not allow:")
			+ "<ul>{0}</ul>".format(lines)
			+ _("Use the <b>Rate Scaled</b> billing mode instead."),
			title=_("Fractional Quantity"),
		)

	if not rows:
		frappe.throw(_("Nothing left to bill on this Sales Order"))

	si.set("items", rows)


def _apply_service_item(si, so, selected, total_portion, service_item):
	if not service_item:
		frappe.throw(_("Select a Milestone Service Item for this billing mode"))

	item_doc = frappe.get_cached_doc("Item", service_item)
	if item_doc.is_stock_item:
		frappe.throw(_("{0} is a stock item. Use a non-stock service item.").format(service_item))

	amount = flt(flt(so.net_total) * total_portion / 100.0, 2)
	labels = ", ".join([(t.payment_term or _("Term {0}").format(t.idx)) for t in selected])

	si.set("items", [])
	si.append(
		"items",
		{
			"item_code": service_item,
			"item_name": item_doc.item_name,
			"description": "{0} - {1} ({2}%)".format(so.name, labels, total_portion),
			"qty": 1,
			"uom": item_doc.stock_uom,
			"stock_uom": item_doc.stock_uom,
			"conversion_factor": 1,
			"rate": amount,
		},
	)


# ---------------------------------------------------------------------------
# Cost center: item + tax -> project General leaf
# ---------------------------------------------------------------------------


def _project_for_so(so):
	if so.get("project"):
		return so.project
	return frappe.db.get_value("Project", {"sales_order": so.name}, "name")


def _apply_project_cost_center(si, project):
	cc = frappe.db.get_value("Project", project, "cost_center")
	si.project = project
	if not cc:
		return
	for item in si.items:
		item.cost_center = cc


def _stamp_tax_cost_center(si, project):
	cc = frappe.db.get_value("Project", project, "cost_center")
	if not cc:
		return
	for tax in si.get("taxes") or []:
		tax.cost_center = cc


# ---------------------------------------------------------------------------
# Invoice's own payment schedule
# ---------------------------------------------------------------------------


def _apply_payment_schedule(si, selected, total_portion):
	si.payment_terms_template = None
	si.set("payment_schedule", [])

	# Invoice is raised today; a stage due date that is already in the past
	# (the SO was placed long ago) would trip ERPNext's "Due Date cannot be
	# before Posting Date" check, so clamp each due date to the posting date.
	posting = getdate(si.posting_date or nowdate())

	count = len(selected)
	running = 0.0

	for i, term in enumerate(selected):
		if i == count - 1:
			portion = flt(100.0 - running, 6)
		else:
			portion = flt(flt(term.invoice_portion) * 100.0 / total_portion, 6)
			running += portion

		due = term.due_date
		if not due or getdate(due) < posting:
			due = posting

		si.append(
			"payment_schedule",
			{
				"payment_term": term.payment_term,
				"description": term.description,
				"due_date": due,
				"mode_of_payment": term.get("mode_of_payment"),
				"invoice_portion": portion,
				"discount_type": term.get("discount_type"),
				"discount": term.get("discount"),
				"discount_date": term.get("discount_date"),
			},
		)


# ---------------------------------------------------------------------------
# doc_events on Sales Invoice: billed status write-back
# ---------------------------------------------------------------------------


def mark_terms_billed(doc, method=None):
	terms = _linked_terms(doc)
	if not terms:
		return

	total_portion = flt(doc.get("sbi_milestone_portion")) or _sum_portions(terms)
	net = flt(doc.net_total)

	for row_name in terms:
		term = frappe.get_doc("Payment Schedule", row_name)
		portion = flt(term.invoice_portion)
		share = flt(net * portion / total_portion, 2) if total_portion else net
		scheduled = flt(term.payment_amount)

		status = "Fully Billed"
		if scheduled and share + 1 < scheduled:
			status = "Partially Billed"

		frappe.db.set_value(
			"Payment Schedule",
			row_name,
			{
				"sbi_billed": 1,
				"sbi_sales_invoice": doc.name,
				"sbi_billed_amount": share,
				"sbi_billed_date": doc.posting_date or nowdate(),
				"sbi_status": status,
			},
			update_modified=False,
		)


def unmark_terms_billed(doc, method=None):
	for row_name in _linked_terms(doc):
		frappe.db.set_value(
			"Payment Schedule",
			row_name,
			{
				"sbi_billed": 0,
				"sbi_sales_invoice": None,
				"sbi_billed_amount": 0,
				"sbi_billed_date": None,
				"sbi_received_amount": 0,
				"sbi_received_date": None,
				"sbi_status": "Pending",
			},
			update_modified=False,
		)


def _sum_portions(term_names):
	total = 0.0
	for name in term_names:
		total += flt(frappe.db.get_value("Payment Schedule", name, "invoice_portion"))
	return total


def _linked_terms(doc):
	raw = doc.get("sbi_source_payment_terms")
	if not raw:
		return []
	try:
		rows = json.loads(raw)
	except Exception:
		return []
	return [r for r in (rows or []) if frappe.db.exists("Payment Schedule", r)]
