"""Recompute payment-schedule amounts on the net total, not the grand total.

By default ERPNext splits the grand total (net + GST) across payment terms.
SBI's contracts quote the payment plan on the net value, with GST shown and
billed separately, so this recomputes each row from net_total after the
standard calculation has run.

Wired on validate for Quotation, Sales Order and Sales Invoice.  Idempotent:
re-running produces the same numbers.
"""

import frappe
from frappe.utils import flt


def set_payment_terms_on_net(doc, method=None):
	schedule = doc.get("payment_schedule") or []
	if not schedule:
		return

	net = flt(doc.get("net_total"))
	if not net:
		return

	# distribute net by each row's invoice_portion; if portions are blank,
	# fall back to the ratio of the existing amount to the grand total.
	grand = flt(doc.get("grand_total")) or flt(doc.get("rounded_total"))

	running = 0.0
	last = len(schedule) - 1
	for i, row in enumerate(schedule):
		portion = flt(row.get("invoice_portion"))
		if portion:
			amount = net * portion / 100.0
		elif grand:
			amount = net * (flt(row.get("payment_amount")) / grand)
		else:
			amount = flt(row.get("payment_amount"))

		amount = flt(amount, 2)

		# put any rounding remainder on the final row so the total is exact
		if i == last:
			amount = flt(net - running, 2)
		running += amount

		row.payment_amount = amount
		if hasattr(row, "base_payment_amount"):
			row.base_payment_amount = amount
		# keep outstanding in step for a fresh (unpaid) document
		if not flt(row.get("paid_amount")):
			row.outstanding = amount