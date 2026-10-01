# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""
Trades and scope sections.

Both were fixed dropdowns, which meant a job needing a trade SBI had not
thought of -- roadworks, compound wall, electrical -- had nowhere to put it.
They are masters now, so anyone can add one without a code change.

Seeded with what the September proposal used. Existing records are never
overwritten, so edits survive a migrate.
"""

import frappe

TRADES = [
	("Civil", 10),
	("PEB", 20),
	("Filling", 30),
	("Piling", 40),
	("Other", 90),
]

SCOPE_SECTIONS = [
	("Client Scope", 10),
	("PEB - Civil Works", 20),
	("PEB", 30),
	("Mezzanine", 40),
	("Other", 90),
]


def setup_boq_trades():
	created = 0
	created += _seed("BOQ Trade", "trade_name", TRADES)
	created += _seed("Scope Section", "section_name", SCOPE_SECTIONS)
	frappe.db.commit()
	return created


def _seed(doctype, namefield, rows):
	if not frappe.db.exists("DocType", doctype):
		return 0

	count = 0
	for name, order in rows:
		if frappe.db.exists(doctype, name):
			continue
		frappe.get_doc({
			"doctype": doctype,
			namefield: name,
			"display_order": order,
			"is_active": 1,
		}).insert(ignore_permissions=True)
		count += 1
	return count
