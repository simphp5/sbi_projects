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

	frappe.clear_cache(doctype=DOCTYPE)
	frappe.db.commit()
	return done
