# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""
Link fields that carry the estimation BOQ down the sales chain.

Estimation Sheet BOQ -> Quotation -> Sales Order -> Project

Without these, once a quotation is raised there is no way back to the sheet
that priced it. With them, any document in the chain can open the others, and
the Sales Order can show a single cockpit for the whole job.

Idempotent; safe on every migrate.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

BOQ_FIELD = {
	"fieldname": "sbi_estimation_boq",
	"label": "Estimation BOQ",
	"fieldtype": "Link",
	"options": "Estimation Sheet BOQ",
	"read_only": 1,
	"no_copy": 0,
	"allow_on_submit": 1,
	"description": "The estimation sheet this document was priced from",
}


def create_peb_link_fields():
	"""Add the BOQ link to Quotation, Sales Order and Project."""
	if not frappe.db.exists("DocType", "Estimation Sheet BOQ"):
		return 0

	fields = {
		"Quotation": [dict(BOQ_FIELD, insert_after="order_type")],
		"Sales Order": [dict(BOQ_FIELD, insert_after="order_type")],
		"Project": [dict(BOQ_FIELD, insert_after="project_name")],
	}

	create_custom_fields(fields, update=True)
	frappe.db.commit()
	return sum(len(v) for v in fields.values())
