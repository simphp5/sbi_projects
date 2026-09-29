# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""
Purchase Invoice tweaks for direct entry.

Most SBI purchases are invoiced straight, without a purchase order first --
material arrives at a site, the bill comes with it, and someone keys it in. Out
of the box that screen fights them a little:

  - the date is called Posting Date and is locked until a checkbox is ticked,
    which is an odd hoop when the bill in your hand has a date on it
  - Project is buried, though it is the field that puts the cost on the right
    site
  - Set Warehouse only appears once Update Stock is ticked

All three are presentation, not logic, so they are done with Property Setters:
no code in the ERPNext form, and an ERPNext upgrade cannot break them.

Idempotent; safe on every migrate.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

DOCTYPE = "Purchase Invoice"

# (fieldname, property, value, property_type)
SETTERS = [
	# the bill in your hand says "invoice date", so call it that
	("posting_date", "label", "Invoice Date", "Data"),

	# tick Edit Posting Date by default, which is what unlocks the date field
	("set_posting_time", "default", "1", "Text"),

	# ...and drop the read-only rule outright, so it is typeable from the start
	("posting_date", "read_only_depends_on", "", "Data"),
	("posting_date", "read_only", "0", "Check"),

	# Project is how a cost lands on the right site -- always show it
	("project", "depends_on", "", "Data"),
	("project", "hidden", "0", "Check"),
	("project", "in_standard_filter", "1", "Check"),

	# and let the warehouse be chosen without hunting for Update Stock first
	("set_warehouse", "depends_on", "", "Data"),
	("set_warehouse", "hidden", "0", "Check"),
	("set_warehouse", "label", "Set Warehouse", "Data"),

	# columns SBI wants on the list
	("project", "in_list_view", "1", "Check"),
	("set_warehouse", "in_list_view", "1", "Check"),
	("posting_date", "in_list_view", "1", "Check"),
	("total_taxes_and_charges", "in_list_view", "1", "Check"),
	("grand_total", "in_list_view", "1", "Check"),
]

# Same treatment on the item rows, so a single invoice can be split across sites.
ITEM_SETTERS = [
	("project", "hidden", "0", "Check"),
	("project", "in_list_view", "1", "Check"),
	("project", "columns", "2", "Int"),
]


def setup_purchase_invoice_fields():
	if not frappe.db.exists("DocType", DOCTYPE):
		return 0

	meta = frappe.get_meta(DOCTYPE)
	done = 0

	for fieldname, prop, value, prop_type in SETTERS:
		if not meta.has_field(fieldname):
			continue
		try:
			make_property_setter(DOCTYPE, fieldname, prop, value, prop_type,
			                     for_doctype=False, validate_fields_for_doctype=False)
			done += 1
		except Exception:
			frappe.log_error(frappe.get_traceback(),
			                 f"PI field setup: {fieldname}.{prop}")

	item_meta = frappe.get_meta("Purchase Invoice Item")
	for fieldname, prop, value, prop_type in ITEM_SETTERS:
		if not item_meta.has_field(fieldname):
			continue
		try:
			make_property_setter("Purchase Invoice Item", fieldname, prop, value,
			                     prop_type, for_doctype=False,
			                     validate_fields_for_doctype=False)
			done += 1
		except Exception:
			frappe.log_error(frappe.get_traceback(),
			                 f"PI item field setup: {fieldname}.{prop}")

	_list_view()

	frappe.clear_cache(doctype=DOCTYPE)
	frappe.db.commit()
	return done


# Columns for the list view, in the order SBI reads them. Days overdue is not
# here because it is not a stored field -- it is worked out against today's
# date, which a list column cannot do. The Purchase Invoice Register report
# carries it, computed live.
LIST_COLUMNS = [
	("project", "Project"),
	("set_warehouse", "Warehouse"),
	("supplier_name", "Supplier"),
	("posting_date", "Invoice Date"),
	("total_taxes_and_charges", "Tax (GST)"),
	("grand_total", "Grand Total"),
	("status", "Status"),
]


def _list_view():
	"""Set the default column order on the Purchase Invoice list.

	Frappe orders list columns by their position in the doctype, so property
	setters alone cannot produce a chosen sequence. List View Settings can:
	it stores the columns as an ordered list, which is also what gets saved
	when someone drags a column in the UI.
	"""
	if not frappe.db.exists("DocType", "List View Settings"):
		return

	meta = frappe.get_meta(DOCTYPE)
	fields = [
		{"fieldname": fn, "label": label}
		for fn, label in LIST_COLUMNS
		if meta.has_field(fn)
	]
	if not fields:
		return

	try:
		if frappe.db.exists("List View Settings", DOCTYPE):
			doc = frappe.get_doc("List View Settings", DOCTYPE)
		else:
			doc = frappe.new_doc("List View Settings")
			doc.name = DOCTYPE

		doc.fields = frappe.as_json(fields)
		if doc.meta.has_field("total_fields"):
			doc.total_fields = str(min(len(fields), 10))

		doc.flags.ignore_permissions = True
		doc.save(ignore_permissions=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "PI list view columns")
