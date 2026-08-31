# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""
Resource master.

`resource` used to be free text on both the Rate Card and the Work Item, which
meant "Mason" and "mason" were different resources and a rate would silently
come back as zero. It is a Link now, and this seeds the master plus repairs the
rows that were entered while it was still text.

Three jobs, all idempotent:
  1. create the starter resources
  2. adopt any name already used on a Rate Card or Work Item that isn't in the
     master yet, so nothing is orphaned by the switch to Link
  3. backfill type / uom / basis on existing child rows, since `fetch_from`
     only fires when a row is edited
"""

import frappe

# (name, resource_type, uom, is_stock)
# is_stock marks what is bought, received and issued from a store. Labour and
# machine hours are costs, not stock, so they never reach a Material Request.
RESOURCES = [
	("Cement", "Material", "bag", 1),
	("M.Sand", "Material", "CUM", 1),
	("P.Sand", "Material", "CUM", 1),
	("20mm Aggregate", "Material", "CUM", 1),
	("Reinforcement", "Material", "Kg", 1),
	("Binding Wire", "Material", "Kg", 1),
	("Bricks", "Material", "Nos", 1),
	("GSB", "Material", "CUM", 1),
	("RMC M25", "Material", "CUM", 1),
	("Water", "Material", "KL", 0),
	("Mason", "Manpower", "Day", 0),
	("M/C (Male Coolie)", "Manpower", "Day", 0),
	("F/C (Female Coolie)", "Manpower", "Day", 0),
	("Site Supervisor", "Manpower", "Day", 0),
	("JCB", "Equipment", "Hour", 0),
	("Crane", "Equipment", "Hour", 0),
	("Vibrator", "Equipment", "Hour", 0),
	("Surveyor", "Manpower", "Day", 0),
	("Erection", "Subcontract", "Kg", 0),
	("Sheet Laying", "Subcontract", "Sqm", 0),
]

CHILD_TABLES = ("Rate Card Item", "Work Item Resource")


def setup_resources():
	if not frappe.db.exists("DocType", "Resource"):
		return 0

	created = _seed()
	adopted = _adopt_existing_names()
	_backfill_child_rows()
	frappe.db.commit()
	return {"created": created, "adopted": adopted}


def _seed():
	count = 0
	for name, rtype, uom, is_stock in RESOURCES:
		if frappe.db.exists("Resource", name):
			continue
		if not frappe.db.exists("Resource Type", rtype):
			continue
		frappe.get_doc({
			"doctype": "Resource",
			"resource_name": name,
			"resource_type": rtype,
			"uom": uom,
			"is_stock": is_stock,
			"is_active": 1,
		}).insert(ignore_permissions=True)
		count += 1
	return count


def _adopt_existing_names():
	"""Create a Resource for any name already in use but not yet in the master.

	Without this, switching `resource` to a Link would leave those rows pointing
	at nothing, and the roll-up would quietly skip them.
	"""
	fallback_type = "Material" if frappe.db.exists("Resource Type", "Material") else None
	adopted = 0

	for table in CHILD_TABLES:
		if not frappe.db.exists("DocType", table):
			continue
		try:
			rows = frappe.db.sql(
				f"""select distinct resource, resource_type, uom
				    from `tab{table}`
				    where ifnull(resource, '') != ''""",
				as_dict=True,
			)
		except Exception:
			continue

		for row in rows:
			name = (row.resource or "").strip()
			if not name or frappe.db.exists("Resource", name):
				continue
			rtype = row.resource_type if frappe.db.exists(
				"Resource Type", row.resource_type or ""
			) else fallback_type
			if not rtype:
				continue
			frappe.get_doc({
				"doctype": "Resource",
				"resource_name": name,
				"resource_type": rtype,
				"uom": row.uom or "Nos",
				"is_active": 1,
				"description": frappe.
				_("Adopted automatically from {0}").format(table),
			}).insert(ignore_permissions=True)
			adopted += 1

	return adopted


def _backfill_child_rows():
	"""Fill type / uom / basis on rows saved before these fields existed.

	`fetch_from` only populates when a row is touched in the UI, so rows created
	by earlier seeds would otherwise show blank Basis and UOM forever.
	"""
	resources = {
		r.name: r
		for r in frappe.get_all(
			"Resource", fields=["name", "resource_type", "uom"]
		)
	}
	if not resources:
		return

	basis_by_type = {
		t.name: t.basis
		for t in frappe.get_all("Resource Type", fields=["name", "basis"])
	}

	for table in CHILD_TABLES:
		if not frappe.db.exists("DocType", table):
			continue
		meta = frappe.get_meta(table)
		has_basis = meta.has_field("basis")

		try:
			rows = frappe.db.sql(
				f"""select name, resource, resource_type, uom
				    from `tab{table}`
				    where ifnull(resource, '') != ''""",
				as_dict=True,
			)
		except Exception:
			continue

		for row in rows:
			res = resources.get((row.resource or "").strip())
			if not res:
				continue

			updates = {}
			if not row.resource_type:
				updates["resource_type"] = res.resource_type
			if not row.uom:
				updates["uom"] = res.uom
			if has_basis:
				updates["basis"] = basis_by_type.get(res.resource_type) or ""

			if updates:
				try:
					frappe.db.set_value(table, row.name, updates, update_modified=False)
				except Exception:
					frappe.log_error(
						frappe.get_traceback(), f"Resource backfill: {table}"
					)
