# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""
Direct sales invoices.

Most SBI invoicing runs through a Sales Order with its twelve payment stages,
and the stage amounts have to add up to the invoice total -- which is exactly
the check that should be there.

But some invoices are not like that. A one-off bill, a reimbursement, a small
job with no order behind it: there are no stages, and being told the stages do
not add up is noise.

The tick clears the payment schedule rather than bypassing the validation. That
matters -- a bypassed check leaves wrong data sitting in the document waiting to
confuse someone later. With nothing in the schedule there is nothing to be
wrong, and ERPNext falls back to a single due date, which is what a direct bill
actually has.

Unticked, nothing changes.
"""

import frappe
from frappe import _
from frappe.utils import add_days, getdate


def clear_payment_schedule(doc, method=None):
	"""validate: drop the payment stages when this is a direct invoice."""
	if not doc.get("sbi_direct_invoice"):
		return

	doc.payment_terms_template = None
	doc.payment_schedule = []

	# a bill with no stages still needs a date it falls due on
	if not doc.get("due_date"):
		days = _credit_days(doc)
		doc.due_date = add_days(getdate(doc.posting_date), days) if days else doc.posting_date


def _credit_days(doc):
	"""Credit days from the customer, then their group. Zero if neither says."""
	try:
		if doc.get("customer"):
			days = frappe.db.get_value("Customer", doc.customer, "payment_terms")
			if days:
				tmpl = frappe.get_all(
					"Payment Terms Template Detail",
					filters={"parent": days},
					fields=["credit_days"],
					order_by="idx asc",
					limit=1,
				)
				if tmpl and tmpl[0].credit_days:
					return int(tmpl[0].credit_days)
	except Exception:
		# a due date is a convenience; never let working it out block a save
		frappe.log_error(frappe.get_traceback(), "Direct invoice: credit days")
	return 0


def create_direct_invoice_field():
	"""Add the tick to Sales Invoice. Idempotent."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	if not frappe.db.exists("DocType", "Sales Invoice"):
		return 0

	create_custom_fields({
		"Sales Invoice": [
			{
				"fieldname": "sbi_direct_invoice",
				"label": "Direct Invoice \u2014 no payment stages",
				"fieldtype": "Check",
				"insert_after": "is_return",
				"default": "0",
				"description": "For a bill with no sales order behind it. Clears the payment "
				               "schedule, so the stage amounts are not checked against the total.",
			},
		]
	}, update=True)

	frappe.db.commit()
	return 1
