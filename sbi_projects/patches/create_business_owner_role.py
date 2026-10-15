# Copyright (c) 2026, Velmaska and contributors
"""Role used by Cash Flow (owner-only dashboard, reports and settings). Created before the
doctypes sync because Cash Flow Settings gives it permissions."""

import frappe


def execute():
	if not frappe.db.exists("Role", "Business Owner"):
		frappe.get_doc({"doctype": "Role", "role_name": "Business Owner", "desk_access": 1}).insert(
			ignore_permissions=True)
