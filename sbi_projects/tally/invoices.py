# Copyright (c) 2026, Velmaska and contributors
"""Tally Sales / Purchase vouchers -> DRAFT Sales / Purchase Invoices.

Tally invoices here carry ledger amounts only (no stock items), so every income / expense
ledger on the voucher becomes one invoice line with a non-stock service item named after
that ledger. GST, round-off, TDS and other ledgers become 'Actual' tax rows. The invoice
total always equals the party amount in Tally.

Anything that does not fit (a second party, an unknown ledger, a note / return voucher)
returns None from invoice_plan(), and the caller books a Journal Entry instead.
"""

import frappe
from frappe.utils import cint, flt

from sbi_projects.tally.common import short

ITEM_PREFIX = "TALLY-"
NOT_ITEM_TYPES = ("Tax", "Round Off", "Bank", "Cash", "Receivable", "Payable", "Stock", "Depreciation",
	"Accumulated Depreciation", "Chargeable")


def invoice_plan(s, v, index):
	"""-> (doctype, party, party_line, other_lines) when this voucher should become an invoice."""
	vt = (v["vtype"] or "").lower()
	if any(w in vt for w in ("credit note", "debit note", "return", "order", "note")):
		return None
	if "sales" in vt and cint(s.get("import_sales_invoices")):
		dt, want = "Sales Invoice", "Customer"
	elif "purchase" in vt and cint(s.get("import_purchase_invoices")):
		dt, want = "Purchase Invoice", "Supplier"
	else:
		return None
	resolved = [(l, index.find(l["ledger"])) for l in v["lines"]]
	parties = [(l, t) for l, t in resolved if t and t[0] == want]
	others = [(l, t) for l, t in resolved if not (t and t[0] == want)]
	if len(parties) != 1 or any(t is None or t[0] != "Account" for _, t in others):
		return None
	line, target = parties[0]
	# sales: customer is debited; purchase: supplier is credited
	if (line["net"] > 0) != (dt == "Sales Invoice"):
		return None
	return dt, target[1], line, [(l, t[1]) for l, t in others]


def _contribution(dt, net):
	"""Amount a line adds to the invoice total."""
	return -net if dt == "Sales Invoice" else net


def service_item(ledger, account, dt, s):
	"""Non-stock item standing for one Tally ledger (e.g. 'TALLY-Sales Works Contract 18%')."""
	code = (ITEM_PREFIX + ledger.strip())[:140]
	if frappe.db.exists("Item", code):
		return code
	hsn = frappe.db.get_value("Account", account, "tally_hsn") if frappe.get_meta("Account").has_field("tally_hsn") else None
	hsn = (hsn or (s.get("default_sales_hsn") if dt == "Sales Invoice" else s.get("default_purchase_hsn")) or "").strip()
	from sbi_projects.tally.importer import _leaf
	group = _leaf("Item Group", s.get("default_item_group") or "All Item Groups", "parent_item_group")
	item = frappe.get_doc({
		"doctype": "Item", "item_code": code, "item_name": ledger.strip()[:140],
		"description": "Tally ledger: " + ledger.strip(), "item_group": group, "stock_uom": "Nos",
		"is_stock_item": 0, "include_item_in_manufacturing": 0, "is_sales_item": 1, "is_purchase_item": 1,
		"tally_ledger_name": ledger.strip(),
	})
	if hsn and item.meta.has_field("gst_hsn_code") and frappe.db.exists("GST HSN Code", hsn):
		item.gst_hsn_code = hsn
	item.flags.ignore_permissions = True
	item.insert()
	return item.name


def make_invoice(s, v, plan, amend_from=None):
	"""Create the DRAFT invoice for a Tally voucher; returns its name. Raises if ERPNext refuses."""
	dt, party, party_line, others = plan
	cost_center = s.get("default_cost_center") or frappe.get_cached_value("Company", s.company, "cost_center")
	items, taxes = [], []
	for line, account in others:
		amount = round(_contribution(dt, line["net"]), 2)
		if not amount:
			continue
		acc_type = frappe.get_cached_value("Account", account, "account_type") or ""
		report = frappe.get_cached_value("Account", account, "report_type")
		if amount > 0 and acc_type not in NOT_ITEM_TYPES and (report == "Profit and Loss" or acc_type == "Fixed Asset"
				or dt == "Purchase Invoice"):
			items.append((line["ledger"], account, amount))
		else:
			taxes.append((line["ledger"], account, amount))
	if not items:
		raise frappe.ValidationError("No income / expense line to use as an invoice item")

	doc = frappe.new_doc(dt)
	doc.company = s.company
	doc.posting_date = v["date"]
	doc.set_posting_time = 1
	if dt == "Sales Invoice":
		doc.customer = party
		doc.due_date = v["date"]
	else:
		doc.supplier = party
		doc.bill_no = short(v["reference"] or v["number"], 140)
		doc.bill_date = v["date"]
		doc.due_date = v["date"]
	if doc.meta.has_field("update_stock"):
		doc.update_stock = 0
	label = (v["vtype"] + " " + v["number"]).strip()
	doc.remarks = ((v["narration"] + "\n") if v["narration"] else "") + "Imported from Tally (" + \
		(s.tally_company or "") + "): " + label
	for field, value in (("tally_guid", v["guid"]), ("tally_voucher", short(label, 140)),
			("tally_alter_id", v["alter_id"]), ("tally_bill_no", short(v["number"], 140)),
			("tally_company", short(s.tally_company, 140)), ("tally_sync_status", "Synced")):
		if doc.meta.has_field(field):
			doc.set(field, value)
	if amend_from:
		doc.amended_from = amend_from
	if doc.meta.has_field("disable_rounded_total"):
		doc.disable_rounded_total = 1  # Tally's own round-off ledger comes in as a tax row

	acc_field = "income_account" if dt == "Sales Invoice" else "expense_account"
	for ledger, account, amount in items:
		doc.append("items", {
			"item_code": service_item(ledger, account, dt, s), "item_name": ledger.strip()[:140],
			"description": ledger.strip(), "qty": 1, "rate": amount, "uom": "Nos", "conversion_factor": 1,
			acc_field: account, "cost_center": cost_center,
		})
	for ledger, account, amount in taxes:
		row = {"charge_type": "Actual", "account_head": account, "description": ledger.strip(),
			"cost_center": cost_center}
		if dt == "Purchase Invoice":
			row.update(category="Total", add_deduct_tax="Add" if amount >= 0 else "Deduct", tax_amount=abs(amount))
		else:
			row["tax_amount"] = amount
		doc.append("taxes", row)

	doc.flags.ignore_permissions = True
	doc.insert()
	expected = round(abs(party_line["net"]), 2)
	if abs(flt(doc.grand_total) - expected) > 1:
		raise frappe.ValidationError("Invoice total " + str(doc.grand_total) + " does not match Tally " + str(expected))
	return doc.name


def remove_doc(doctype, name):
	"""Draft -> deleted; submitted -> cancelled. Used when Tally changes or deletes the voucher."""
	if not frappe.db.exists(doctype, name):
		return
	doc = frappe.get_doc(doctype, name)
	doc.flags.ignore_permissions = True
	if doc.docstatus == 1:
		doc.cancel()
	elif doc.docstatus == 0:
		frappe.delete_doc(doctype, name, ignore_permissions=True, force=True)
