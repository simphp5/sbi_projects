# Copyright (c) 2026, Velmaska and contributors
"""Auto receipt tracking for milestone billing.

When a Payment Entry is submitted (or cancelled) against a milestone Sales
Invoice, roll the received amount up to the source Sales Order's Payment
Schedule rows and update their status:

    received >= billed  -> Fully Received
    0 < received < billed -> Partially Received

Wired on Payment Entry on_submit / on_cancel.
"""

import json

import frappe
from frappe.utils import flt


def update_received_on_submit(doc, method=None):
	_recompute_for_payment(doc)


def update_received_on_cancel(doc, method=None):
	_recompute_for_payment(doc)


def _recompute_for_payment(payment_entry):
	"""Find milestone invoices referenced by this payment and refresh the
	received figures on their source payment-schedule rows."""
	invoices = {
		ref.reference_name
		for ref in (payment_entry.get("references") or [])
		if ref.reference_doctype == "Sales Invoice" and ref.reference_name
	}
	for inv in invoices:
		_refresh_invoice_receipts(inv)


def _refresh_invoice_receipts(invoice_name):
	si = frappe.db.get_value(
		"Sales Invoice",
		invoice_name,
		["docstatus", "sbi_source_payment_terms", "sbi_milestone_portion", "net_total"],
		as_dict=True,
	)
	if not si or not si.sbi_source_payment_terms:
		return

	try:
		term_names = json.loads(si.sbi_source_payment_terms)
	except Exception:
		return
	term_names = [t for t in (term_names or []) if frappe.db.exists("Payment Schedule", t)]
	if not term_names:
		return

	# total paid against this invoice (allocated, submitted payments only)
	paid = flt(
		frappe.db.sql(
			"""
			SELECT COALESCE(SUM(per.allocated_amount), 0)
			FROM `tabPayment Entry Reference` per
			INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
			WHERE per.reference_doctype = 'Sales Invoice'
			  AND per.reference_name = %s
			  AND pe.docstatus = 1
			""",
			invoice_name,
		)[0][0]
	)

	total_portion = flt(si.sbi_milestone_portion) or _sum_portions(term_names)

	for row_name in term_names:
		term = frappe.get_doc("Payment Schedule", row_name)
		portion = flt(term.invoice_portion)
		# this row's slice of the invoice's receipts, capped at what was billed
		billed = flt(term.get("sbi_billed_amount"))
		received = flt(paid * portion / total_portion, 2) if total_portion else paid
		if billed and received > billed:
			received = billed

		status = term.get("sbi_status") or "Fully Billed"
		received_date = None
		if received > 0:
			received_date = _last_payment_date(invoice_name)
			if billed and received + 1 >= billed:
				status = "Fully Received"
			else:
				status = "Partially Received"
		elif term.get("sbi_billed"):
			# payment cancelled back to zero -> revert to billed status
			status = "Fully Billed" if _is_full(term) else "Partially Billed"

		frappe.db.set_value(
			"Payment Schedule",
			row_name,
			{
				"sbi_received_amount": received,
				"sbi_received_date": received_date,
				"sbi_status": status,
			},
			update_modified=False,
		)


def _is_full(term):
	scheduled = flt(term.get("payment_amount"))
	billed = flt(term.get("sbi_billed_amount"))
	return not scheduled or billed + 1 >= scheduled


def _last_payment_date(invoice_name):
	return frappe.db.sql(
		"""
		SELECT MAX(pe.posting_date)
		FROM `tabPayment Entry Reference` per
		INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
		WHERE per.reference_doctype = 'Sales Invoice'
		  AND per.reference_name = %s
		  AND pe.docstatus = 1
		""",
		invoice_name,
	)[0][0]


def _sum_portions(term_names):
	total = 0.0
	for name in term_names:
		total += flt(frappe.db.get_value("Payment Schedule", name, "invoice_portion"))
	return total
