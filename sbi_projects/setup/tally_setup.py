# Copyright (c) 2026, Velmaska and contributors
"""Tally integration: custom fields, agent role, number cards, charts and workspace.

Runs on every migrate (via install.after_install). Idempotent.
"""

import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MODULE = "SBI Projects"
WORKSPACE = "Tally Integration"
VOUCHER_DOCTYPES = ("Sales Invoice", "Purchase Invoice", "Payment Entry", "Journal Entry")


def setup_tally():
	_role()
	_custom_fields()
	_cards_and_charts()
	_workspace()
	frappe.db.commit()


def _role():
	if not frappe.db.exists("Role", "Tally Agent"):
		frappe.get_doc({"doctype": "Role", "role_name": "Tally Agent", "desk_access": 0}).insert(
			ignore_permissions=True)


def _sync_fields(extra=None):
	fields = [
		{"fieldname": "tally_section", "label": "Tally", "fieldtype": "Section Break", "collapsible": 1},
		{"fieldname": "tally_sync_status", "label": "Tally Sync Status", "fieldtype": "Select",
			"options": "\nSynced\nFailed\nRetry\nSkip", "allow_on_submit": 1, "no_copy": 1,
			"in_standard_filter": 1, "insert_after": "tally_section",
			"description": "Blank = waiting to be sent. After fixing a Failed record set Retry. Skip = never send."},
		{"fieldname": "tally_synced_on", "label": "Tally Synced On", "fieldtype": "Datetime", "read_only": 1,
			"allow_on_submit": 1, "no_copy": 1, "insert_after": "tally_sync_status"},
		{"fieldname": "tally_col", "fieldtype": "Column Break", "insert_after": "tally_synced_on"},
		{"fieldname": "tally_sync_error", "label": "Tally Sync Error", "fieldtype": "Small Text", "read_only": 1,
			"allow_on_submit": 1, "no_copy": 1, "insert_after": "tally_col"},
	]
	return fields + (extra or [])


def _master_fields(after=None):
	return [
		{"fieldname": "tally_ledger_name", "label": "Tally Name", "fieldtype": "Data", "no_copy": 1,
			"insert_after": after, "description": "Name of this record in Tally, if different. Filled automatically when synced."},
		{"fieldname": "tally_guid", "label": "Tally GUID", "fieldtype": "Data", "read_only": 1, "no_copy": 1,
			"hidden": 1, "insert_after": "tally_ledger_name"},
	]


def _custom_fields():
	je_extra = [
		{"fieldname": "tally_voucher", "label": "Tally Voucher", "fieldtype": "Data", "read_only": 1,
			"allow_on_submit": 1, "no_copy": 1, "in_standard_filter": 1, "insert_after": "tally_sync_error",
			"description": "Set when this entry was created from a Tally voucher."},
		{"fieldname": "tally_guid", "label": "Tally GUID", "fieldtype": "Data", "read_only": 1,
			"allow_on_submit": 1, "no_copy": 1, "search_index": 1, "insert_after": "tally_voucher"},
		{"fieldname": "tally_alter_id", "label": "Tally Alter ID", "fieldtype": "Int", "read_only": 1,
			"allow_on_submit": 1, "no_copy": 1, "hidden": 1, "insert_after": "tally_guid"},
	]
	fields = {dt: _sync_fields() for dt in VOUCHER_DOCTYPES if dt != "Journal Entry"}
	fields["Journal Entry"] = _sync_fields(je_extra)
	fields["Account"] = _master_fields("account_type")
	fields["Customer"] = _master_fields("customer_group")
	fields["Supplier"] = _master_fields("supplier_group")
	fields["Item"] = _master_fields("item_group")
	for dt, rows in fields.items():
		for row in rows:
			if not row.get("insert_after") or not _field_exists(dt, row["insert_after"], rows):
				row.pop("insert_after", None)
	create_custom_fields(fields, ignore_validate=True)


def _field_exists(dt, fieldname, own_rows):
	if any(r["fieldname"] == fieldname for r in own_rows):
		return True
	return frappe.get_meta(dt).has_field(fieldname)


# ---------------------------------------------------------------- dashboard
def _filters(*conds):
	return json.dumps([["Tally Sync Log", f, "=", v, False] for f, v in conds])


NUMBER_CARDS = [
	{"label": "Tally Waiting to Send", "type": "Custom", "method": "sbi_projects.tally.admin.pending_export_count",
		"color": "#2490EF"},
	{"label": "Tally Exported", "type": "Document Type", "document_type": "Tally Sync Log", "function": "Count",
		"filters_json": _filters(("direction", "Export"), ("status", "Success")), "color": "#29CD42"},
	{"label": "Tally Imported", "type": "Document Type", "document_type": "Tally Sync Log", "function": "Count",
		"filters_json": _filters(("direction", "Import"), ("status", "Success")), "color": "#29CD42"},
	{"label": "Tally Failed", "type": "Document Type", "document_type": "Tally Sync Log", "function": "Count",
		"filters_json": _filters(("status", "Failed")), "color": "#E24C4C"},
]

CHARTS = [
	{"chart_name": "Tally Sent per Day", "chart_type": "Count", "document_type": "Tally Sync Log",
		"based_on": "synced_on", "timeseries": 1, "timespan": "Last Month", "time_interval": "Daily",
		"type": "Bar", "filters_json": _filters(("direction", "Export"), ("status", "Success")), "color": "#2490EF"},
	{"chart_name": "Tally Received per Day", "chart_type": "Count", "document_type": "Tally Sync Log",
		"based_on": "synced_on", "timeseries": 1, "timespan": "Last Month", "time_interval": "Daily",
		"type": "Bar", "filters_json": _filters(("direction", "Import"), ("status", "Success")), "color": "#7575FF"},
	{"chart_name": "Tally Records by Type", "chart_type": "Group By", "document_type": "Tally Sync Log",
		"group_by_type": "Count", "group_by_based_on": "record_type", "timeseries": 0,
		"type": "Donut", "filters_json": "[]"},
	{"chart_name": "Tally Records by Status", "chart_type": "Group By", "document_type": "Tally Sync Log",
		"group_by_type": "Count", "group_by_based_on": "status", "timeseries": 0,
		"type": "Pie", "filters_json": "[]"},
]


def _upsert(doctype, name, values):
	if frappe.db.exists(doctype, name):
		doc = frappe.get_doc(doctype, name)
		doc.update(values)
		doc.flags.ignore_permissions = True
		doc.save()
	else:
		doc = frappe.get_doc(dict(values, doctype=doctype))
		doc.flags.ignore_permissions = True
		doc.insert()


def _cards_and_charts():
	for card in NUMBER_CARDS:
		values = dict(card, is_public=1, module=MODULE, show_percentage_stats=0)
		_upsert("Number Card", card["label"], values)
	for chart in CHARTS:
		values = dict(chart, is_public=1, module=MODULE)
		_upsert("Dashboard Chart", chart["chart_name"], values)


# ---------------------------------------------------------------- workspace
LINK_CARDS = [
	("Setup", [("Tally Settings", "Connection, agent key, group map, opening balances"),
		("Account", "Tally ledgers"), ("Customer", "Sundry Debtors"), ("Supplier", "Sundry Creditors"),
		("Item", "Tally stock items")]),
	("Records", [("Tally Sync Log", "Every record sent or received"),
		("Journal Entry", "Tally vouchers arrive here"), ("Sales Invoice", "Sent as Sales vouchers"),
		("Purchase Invoice", "Sent as Purchase vouchers"), ("Payment Entry", "Sent as Receipt / Payment")]),
]


def _workspace():
	if not frappe.db.exists("DocType", "Workspace"):
		return
	doc = frappe.get_doc("Workspace", WORKSPACE) if frappe.db.exists("Workspace", WORKSPACE) \
		else frappe.new_doc("Workspace")
	doc.name = doc.name or WORKSPACE
	doc.label = WORKSPACE
	doc.title = WORKSPACE
	doc.module = MODULE
	doc.icon = "refresh"
	doc.public = 1
	doc.is_hidden = 0
	doc.links, doc.shortcuts, doc.number_cards, doc.charts = [], [], [], []

	if frappe.db.exists("Page", "tally-dashboard"):
		doc.append("shortcuts", {"type": "Page", "link_to": "tally-dashboard", "label": "Tally Dashboard",
			"color": "Green"})
	for label in ("Tally Settings", "Tally Sync Log"):
		doc.append("shortcuts", {"type": "DocType", "link_to": label, "label": label,
			"color": "Blue" if label == "Tally Settings" else "Grey", "doc_view": "List" if label == "Tally Sync Log" else ""})
	for card in NUMBER_CARDS:
		doc.append("number_cards", {"number_card_name": card["label"], "label": card["label"]})
	for chart in CHARTS:
		doc.append("charts", {"chart_name": chart["chart_name"], "label": chart["chart_name"]})
	for card_label, links in LINK_CARDS:
		doc.append("links", {"type": "Card Break", "label": card_label, "link_count": len(links)})
		for dt, note in links:
			doc.append("links", {"type": "Link", "label": dt, "link_type": "DocType", "link_to": dt,
				"description": note, "onboard": 0, "is_query_report": 0})

	blocks = [_block("header", {"text": '<span class="h4"><b>Tally Integration</b></span>', "col": 12})]
	blocks += [_block("number_card", {"number_card_name": c["label"], "col": 3}) for c in NUMBER_CARDS]
	blocks += [_block("chart", {"chart_name": c["chart_name"], "col": 6}) for c in CHARTS]
	blocks += [_block("spacer", {"col": 12})]
	blocks += [_block("shortcut", {"shortcut_name": s, "col": 3})
		for s in ("Tally Dashboard", "Tally Settings", "Tally Sync Log")
		if s != "Tally Dashboard" or frappe.db.exists("Page", "tally-dashboard")]
	blocks += [_block("spacer", {"col": 12})]
	blocks += [_block("card", {"card_name": c, "col": 6}) for c, _ in LINK_CARDS]
	doc.content = json.dumps(blocks)

	doc.flags.ignore_permissions = True
	doc.flags.ignore_links = True
	doc.save(ignore_permissions=True)


def _block(block_type, data):
	return {"id": frappe.generate_hash(length=10), "type": block_type, "data": data}
