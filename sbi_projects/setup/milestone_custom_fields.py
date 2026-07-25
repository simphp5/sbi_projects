# Copyright (c) 2026, Velmaska and contributors
"""Custom fields required by milestone billing.

Called from sbi_projects.setup.install.after_install(), which is also wired to
the after_migrate hook - so these are created/updated on every deploy.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MILESTONE_CUSTOM_FIELDS = {
	# Payment Schedule is a shared child table (SO / SI / PO / PI).
	# The flags below are only ever written by milestone billing.
	"Payment Schedule": [
		{
			"fieldname": "sbi_billed",
			"label": "Billed",
			"fieldtype": "Check",
			"insert_after": "payment_amount",
			"read_only": 1,
			"allow_on_submit": 1,
			"no_copy": 1,
			"in_list_view": 0,
		},
		{
			"fieldname": "sbi_sales_invoice",
			"label": "Milestone Invoice",
			"fieldtype": "Data",
			"insert_after": "sbi_billed",
			"read_only": 1,
			"allow_on_submit": 1,
			"no_copy": 1,
		},
	],
	"Sales Invoice": [
		{
			"fieldname": "sbi_milestone_section",
			"label": "Milestone Billing",
			"fieldtype": "Section Break",
			"insert_after": "payment_schedule",
			"collapsible": 1,
		},
		{
			"fieldname": "sbi_source_sales_order",
			"label": "Milestone Source Sales Order",
			"fieldtype": "Link",
			"options": "Sales Order",
			"insert_after": "sbi_milestone_section",
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "sbi_milestone_portion",
			"label": "Billed Portion (%)",
			"fieldtype": "Percent",
			"insert_after": "sbi_source_sales_order",
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "sbi_source_payment_terms",
			"label": "Source Payment Term Rows",
			"fieldtype": "Small Text",
			"insert_after": "sbi_milestone_portion",
			"read_only": 1,
			"hidden": 1,
			"no_copy": 1,
		},
	],
}


def create_milestone_custom_fields():
	create_custom_fields(MILESTONE_CUSTOM_FIELDS, ignore_validate=True, update=True)
	frappe.db.commit()
