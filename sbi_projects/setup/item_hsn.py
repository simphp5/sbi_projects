import frappe

GROUP_FIELD = "sbi_default_hsn"


def group_hsn(item_group):
	"""Walk up the Item Group tree until a default HSN is found."""
	seen = set()
	while item_group and item_group not in seen:
		seen.add(item_group)
		row = frappe.db.get_value(
			"Item Group", item_group, [GROUP_FIELD, "parent_item_group"], as_dict=True
		)
		if not row:
			return None
		if row.get(GROUP_FIELD):
			return row.get(GROUP_FIELD)
		item_group = row.get("parent_item_group")
	return None


def item_validate(doc, method=None):
	"""Fill HSN/SAC from the Item Group default when the item has none."""
	if doc.get("gst_hsn_code"):
		return
	if not doc.meta.has_field("gst_hsn_code"):
		return
	hsn = group_hsn(doc.get("item_group"))
	if hsn:
		doc.gst_hsn_code = hsn


@frappe.whitelist()
def backfill_item_hsn(item_group=None, dry_run=0):
	"""Apply Item Group defaults to every item that has no HSN yet."""
	frappe.only_for("System Manager")

	filters = {"gst_hsn_code": ["in", ["", None]]}
	if item_group:
		filters["item_group"] = item_group

	rows = frappe.get_all(
		"Item", filters=filters, fields=["name", "item_group"], limit_page_length=0
	)

	updated = []
	missing = []
	for row in rows:
		hsn = group_hsn(row.item_group)
		if hsn:
			if not int(dry_run or 0):
				frappe.db.set_value(
					"Item", row.name, "gst_hsn_code", hsn, update_modified=False
				)
			updated.append({"item": row.name, "group": row.item_group, "hsn": hsn})
		else:
			missing.append({"item": row.name, "group": row.item_group})

	if not int(dry_run or 0):
		frappe.db.commit()

	return {
		"scanned": len(rows),
		"updated": len(updated),
		"updated_sample": updated[:25],
		"no_group_default": missing[:50],
		"no_group_default_count": len(missing),
		"dry_run": bool(int(dry_run or 0)),
	}


@frappe.whitelist()
def set_group_defaults(mapping):
	"""mapping: {"Cement": "2523", "Steel": "7214", ...}"""
	frappe.only_for("System Manager")
	if isinstance(mapping, str):
		import json

		mapping = json.loads(mapping)

	done = []
	skipped = []
	for group, hsn in mapping.items():
		if not frappe.db.exists("Item Group", group):
			skipped.append({"group": group, "reason": "Item Group not found"})
			continue
		if not frappe.db.exists("GST HSN Code", hsn):
			skipped.append({"group": group, "reason": "HSN %s not in master" % hsn})
			continue
		frappe.db.set_value("Item Group", group, GROUP_FIELD, hsn)
		done.append({"group": group, "hsn": hsn})

	frappe.db.commit()
	return {"set": done, "skipped": skipped}
