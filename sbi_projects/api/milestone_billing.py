# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""Milestone billing: create a Sales Invoice for one or more selected
Payment Schedule rows of a submitted Sales Order.
"""

import json

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice


# ---------------------------------------------------------------------------
# Read: payment terms of a Sales Order
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_payment_terms(sales_order):
	"""Return every Payment Schedule row of a submitted Sales Order with its
	billed / un-billed state, for the milestone selection dialog."""

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

	rows = []
	for row in so.payment_schedule:
		rows.append(
			{
				"row_name": row.name,
				"idx": row.idx,
				"payment_term": row.payment_term or _("Term {0}").format(row.idx),
				"description": row.description,
				"due_date": row.due_date,
				"invoice_portion": flt(row.invoice_portion),
				"payment_amount": flt(row.payment_amount),
				"billed": 1 if row.get("sbi_billed") else 0,
				"sales_invoice": row.get("sbi_sales_invoice"),
			}
		)
	return rows


# ---------------------------------------------------------------------------
# Write: build the milestone Sales Invoice
# ---------------------------------------------------------------------------


@frappe.whitelist()
def make_milestone_invoice(
	sales_order, selected_rows, billing_mode="Proportional Qty", service_item=None
):
	"""Create (but do not save) a draft Sales Invoice covering the selected
	Payment Schedule rows of ``sales_order``.

	billing_mode:
	    "Proportional Qty"    -> every SO item is billed at (selected %) of its
	                             original qty. Keeps HSN / GST / SO % Billed intact.
	    "Single Service Item" -> one consolidated service line for the selected
	                             amount. Use for advance / erection milestones.
	"""

	if isinstance(selected_rows, str):
		selected_rows = json.loads(selected_rows)

	if not selected_rows:
		frappe.throw(_("Select at least one Payment Term"))

	so = frappe.get_doc("Sales Order", sales_order)
	so.check_permission("read")

	selected = _resolve_terms(so, selected_rows)

	total_portion = flt(sum(flt(t.invoice_portion) for t in selected), 6)
	if total_portion <= 0:
		frappe.throw(_("Selected Payment Terms have zero Invoice Portion"))

	si = make_sales_invoice(sales_order)

	if billing_mode == "Single Service Item":
		_apply_service_item(si, so, selected, total_portion, service_item)
	else:
		_apply_proportional_qty(si, so, total_portion / 100.0)

	_apply_payment_schedule(si, selected, total_portion)

	si.sbi_source_sales_order = so.name
	si.sbi_milestone_portion = total_portion
	si.sbi_source_payment_terms = json.dumps([t.name for t in selected])

	si.run_method("calculate_taxes_and_totals")
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


def _apply_proportional_qty(si, so, factor):
	"""Scale every invoice line against the ORIGINAL Sales Order qty.

	make_sales_invoice() hands us the *remaining* qty; scaling that by the
	factor would compound across milestones, so we always recompute from the
	Sales Order Item qty.
	"""
	so_qty = {d.name: flt(d.qty) for d in so.items}
	precision = frappe.get_precision("Sales Invoice Item", "qty") or 3

	rows = []
	for item in si.items:
		base_qty = so_qty.get(item.so_detail)
		if base_qty is None:
			# line not traceable to the SO - keep it untouched
			rows.append(item)
			continue

		item.qty = flt(base_qty * factor, precision)
		if flt(item.qty) > 0:
			rows.append(item)

	if not rows:
		frappe.throw(_("Nothing left to bill on this Sales Order"))

	si.set("items", rows)


def _apply_service_item(si, so, selected, total_portion, service_item):
	"""Replace all lines with a single consolidated milestone service line."""
	if not service_item:
		frappe.throw(_("Select a Milestone Service Item for this billing mode"))

	item_doc = frappe.get_cached_doc("Item", service_item)
	if item_doc.is_stock_item:
		frappe.throw(_("{0} is a stock item. Use a non-stock service item.").format(service_item))

	amount = flt(flt(so.net_total) * total_portion / 100.0, 2)
	labels = ", ".join([(t.payment_term or _("Term {0}").format(t.idx)) for t in selected])

	cost_center = so.items[0].cost_center if so.items else None

	si.set("items", [])
	si.append(
		"items",
		{
			"item_code": service_item,
			"item_name": item_doc.item_name,
			"description": "{0} — {1} ({2}%)".format(so.name, labels, total_portion),
			"qty": 1,
			"uom": item_doc.stock_uom,
			"stock_uom": item_doc.stock_uom,
			"conversion_factor": 1,
			"rate": amount,
			"cost_center": cost_center,
			"project": so.project,
		},
	)


def _apply_payment_schedule(si, selected, total_portion):
	"""Rebuild the invoice's own Payment Schedule from the selected SO terms,
	re-normalised so the portions add up to exactly 100%."""
	si.payment_terms_template = None
	si.set("payment_schedule", [])

	count = len(selected)
	running = 0.0

	for i, term in enumerate(selected):
		if i == count - 1:
			portion = flt(100.0 - running, 6)
		else:
			portion = flt(flt(term.invoice_portion) * 100.0 / total_portion, 6)
			running += portion

		si.append(
			"payment_schedule",
			{
				"payment_term": term.payment_term,
				"description": term.description,
				"due_date": term.due_date,
				"mode_of_payment": term.get("mode_of_payment"),
				"invoice_portion": portion,
				"discount_type": term.get("discount_type"),
				"discount": term.get("discount"),
				"discount_date": term.get("discount_date"),
			},
		)


# ---------------------------------------------------------------------------
# doc_events on Sales Invoice
# ---------------------------------------------------------------------------


def mark_terms_billed(doc, method=None):
	"""on_submit: flag the source Sales Order payment terms as billed."""
	for row_name in _linked_terms(doc):
		frappe.db.set_value(
			"Payment Schedule",
			row_name,
			{"sbi_billed": 1, "sbi_sales_invoice": doc.name},
			update_modified=False,
		)


def unmark_terms_billed(doc, method=None):
	"""on_cancel: release the payment terms so they can be re-billed."""
	for row_name in _linked_terms(doc):
		frappe.db.set_value(
			"Payment Schedule",
			row_name,
			{"sbi_billed": 0, "sbi_sales_invoice": None},
			update_modified=False,
		)


def _linked_terms(doc):
	raw = doc.get("sbi_source_payment_terms")
	if not raw:
		return []
	try:
		rows = json.loads(raw)
	except Exception:
		return []
	return [r for r in (rows or []) if frappe.db.exists("Payment Schedule", r)]
