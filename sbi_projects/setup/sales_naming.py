import frappe
from frappe.model.naming import getseries, make_autoname
from frappe.utils import getdate, nowdate

# naming_series values that trigger the SBI/000/FY pattern
SBI_PREFIXES = ("SBI/", "SBIPPL/")


def fiscal_year_short(date=None):
	"""2026-04-01 -> '2026-27'"""
	date = getdate(date or nowdate())
	name = frappe.db.get_value(
		"Fiscal Year",
		{"year_start_date": ["<=", date], "year_end_date": [">=", date]},
		"name",
	)
	if name:
		parts = str(name).replace(" ", "").split("-")
		if len(parts) == 2 and len(parts[0]) == 4:
			return "%s-%s" % (parts[0], parts[1][-2:])
		return str(name)

	start = date.year if date.month >= 4 else date.year - 1
	return "%d-%02d" % (start, (start + 1) % 100)


def _sbi_name(prefix, date):
	fy = fiscal_year_short(date)
	key = "%s%s" % (prefix, fy)
	number = getseries(key, 3)
	return "%s%s/%s" % (prefix, number, fy)


def _autoname(doc, date_field):
	series = doc.get("naming_series") or ""
	if series in SBI_PREFIXES:
		doc.name = _sbi_name(series, doc.get(date_field))
	elif series:
		doc.name = make_autoname(series, doc.doctype, doc)


def sales_order_autoname(doc, method=None):
	_autoname(doc, "transaction_date")


def sales_invoice_autoname(doc, method=None):
	_autoname(doc, "posting_date")


# ---------------------------------------------------------------- stage stamp


def sales_invoice_validate(doc, method=None):
	"""Copy stage number / reference no onto the parent for list view + print."""
	from sbi_projects.utils.print_helpers import stage_parts

	stage_no = None
	stage_name = None
	for row in doc.get("items") or []:
		no, name, _portion = stage_parts(row)
		if no and not stage_no:
			stage_no = no
		if name and not stage_name:
			stage_name = name
		if stage_no:
			break

	if doc.meta.has_field("sbi_stage_no"):
		doc.sbi_stage_no = str(stage_no) if stage_no else ""
	if doc.meta.has_field("sbi_stage_name"):
		doc.sbi_stage_name = stage_name or ""

	# Reference No. & Date -> pull Customer Order No from the linked Sales Order
	if not doc.get("po_no"):
		for row in doc.get("items") or []:
			if row.get("sales_order"):
				so = frappe.db.get_value(
					"Sales Order", row.sales_order, ["po_no", "po_date"], as_dict=True
				)
				if so and so.po_no:
					doc.po_no = so.po_no
					if not doc.get("po_date") and so.po_date:
						doc.po_date = so.po_date
				break
