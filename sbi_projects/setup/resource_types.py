# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""
Resource Type master.

The starter set covers what SBI books today. It is a master, not a hard-coded
list, so anyone can add Consumables, Insurance, Scaffolding or whatever else a
job needs without a code change -- which is the whole point of it being a
DocType rather than a Select field.

`basis` decides how a row is costed:
    Quantity  amount = qty x rate                (cement, steel)
    Days      amount = nos x days x rate         (6 masons for 30 days)
    Hours     amount = nos x hours x rate        (JCB for 12 hours)
    Trips     amount = trips x rate              (tipper loads)
    Lumpsum   amount = rate                      (mobilisation)

`cost_category` maps a type to the site cost-centre leaf, so estimated and
actual land in the same bucket and variance means something.

Idempotent; existing rows keep any edits.
"""

import frappe

# (name, basis, cost_category, order, description)
RESOURCE_TYPES = [
	("Material", "Quantity", "Material", 10,
	 "Cement, sand, aggregate, steel, blocks -- anything consumed by quantity."),
	("Manpower", "Days", "Manpower", 20,
	 "Skilled and unskilled labour costed per head per day."),
	("Equipment", "Hours", "Equipment Rent", 30,
	 "Owned or hired plant costed by running hours."),
	("Transport", "Trips", "Material", 40,
	 "Tippers, trailers and lead charges costed per trip."),
	("Subcontract", "Quantity", "Subcontracting", 50,
	 "Work given out on rate -- shuttering, painting, erection."),
	("Overheads", "Lumpsum", "Overheads", 60,
	 "Site establishment, supervision, insurance and similar."),
]


def setup_resource_types():
	if not frappe.db.exists("DocType", "Resource Type"):
		return 0

	created = 0
	for name, basis, category, order, description in RESOURCE_TYPES:
		if frappe.db.exists("Resource Type", name):
			continue
		frappe.get_doc({
			"doctype": "Resource Type",
			"resource_type_name": name,
			"basis": basis,
			"cost_category": category,
			"display_order": order,
			"description": description,
			"is_active": 1,
		}).insert(ignore_permissions=True)
		created += 1

	_migrate_legacy_names()
	frappe.db.commit()
	return created


def _migrate_legacy_names():
	"""Point old Select values at the new master.

	Rate Card Item and Work Item Resource used a Select with slightly different
	wording. Those rows now hold a Link, so the old text has to line up with a
	real Resource Type or the link breaks.
	"""
	renames = {
		"Labour": "Manpower",
		"Machinery": "Equipment",
		"Subcontractor": "Subcontract",
	}
	for table in ("Rate Card Item", "Work Item Resource"):
		if not frappe.db.exists("DocType", table):
			continue
		for old, new in renames.items():
			try:
				frappe.db.sql(
					f"update `tab{table}` set resource_type = %s where resource_type = %s",
					(new, old),
				)
			except Exception:
				frappe.log_error(
					frappe.get_traceback(), f"Resource Type migration: {table}"
				)
