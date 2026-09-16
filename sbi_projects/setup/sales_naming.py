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
		no, name, _portion = stage_parts(row, doc)
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
		from sbi_projects.utils.print_helpers import linked_sales_order

		so_name = linked_sales_order(doc)
		if so_name:
			so = frappe.db.get_value(
				"Sales Order", so_name, ["po_no", "po_date", "transaction_date"], as_dict=True
			)
			if so and so.po_no:
				doc.po_no = so.po_no
				if not doc.get("po_date"):
					doc.po_date = so.po_date or so.transaction_date


@frappe.whitelist()
def backfill_stage_no(limit=500):
	"""Stamp Stage No / Stage Name on existing Sales Invoices (drafts + submitted)."""
	from sbi_projects.utils.print_helpers import linked_sales_order, stage_parts

	frappe.only_for("System Manager")
	names = frappe.get_all(
		"Sales Invoice",
		filters={"docstatus": ["<", 2]},
		pluck="name",
		order_by="creation desc",
		limit_page_length=int(limit),
	)

	updated = 0
	for name in names:
		doc = frappe.get_doc("Sales Invoice", name)
		stage_no = None
		stage_name = None
		for row in doc.get("items") or []:
			no, sname, _portion = stage_parts(row, doc)
			if no and not stage_no:
				stage_no = no
			if sname and not stage_name:
				stage_name = sname
			if stage_no:
				break

		po_no = doc.get("po_no")
		po_date = doc.get("po_date")
		if not po_no:
			so_name = linked_sales_order(doc)
			if so_name:
				so = frappe.db.get_value(
					"Sales Order", so_name, ["po_no", "po_date", "transaction_date"], as_dict=True
				)
				if so and so.po_no:
					po_no = so.po_no
					po_date = po_date or so.po_date or so.transaction_date

		values = {
			"sbi_stage_no": str(stage_no) if stage_no else "",
			"sbi_stage_name": stage_name or "",
		}
		if po_no:
			values["po_no"] = po_no
			if po_date:
				values["po_date"] = po_date

		changed = any(doc.get(k) != v for k, v in values.items())
		if changed:
			frappe.db.set_value("Sales Invoice", name, values, update_modified=False)
			updated += 1

	frappe.db.commit()
	return {"scanned": len(names), "updated": updated}
