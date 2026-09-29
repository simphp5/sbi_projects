# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""
Proposal fields on the Quotation.

SBI's proposal does not show the priced BOQ. The client reads project details,
a four-line commercial summary, the scope matrix and the payment stages -- and
nothing else. The print format therefore needs all of that on the Quotation
itself, which is what these fields carry.

They are filled automatically when a quotation is created from a BOQ, and can
be edited afterwards without touching the estimate.

Idempotent; safe on every migrate.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def create_quotation_proposal_fields():
	if not frappe.db.exists("DocType", "Quotation"):
		return 0
	if not frappe.db.exists("DocType", "Estimation Sheet BOQ Scope"):
		return 0

	fields = {
		"Quotation": [
			{
				"fieldname": "sbi_proposal_tab",
				"label": "Proposal",
				"fieldtype": "Tab Break",
				"insert_after": "terms",
			},
			{
				"fieldname": "sbi_project_title",
				"label": "Project",
				"fieldtype": "Data",
				"insert_after": "sbi_proposal_tab",
				"description": "Workshop building, Warehouse ...",
			},
			{
				"fieldname": "sbi_client_name",
				"label": "Client",
				"fieldtype": "Data",
				"insert_after": "sbi_project_title",
			},
			{
				"fieldname": "sbi_location",
				"label": "Location",
				"fieldtype": "Data",
				"insert_after": "sbi_client_name",
			},
			{
				"fieldname": "sbi_scope_note",
				"label": "Scope",
				"fieldtype": "Data",
				"insert_after": "sbi_location",
			},
			{
				"fieldname": "sbi_proposal_cb",
				"fieldtype": "Column Break",
				"insert_after": "sbi_scope_note",
			},
			{
				"fieldname": "sbi_area_note",
				"label": "Area of Building",
				"fieldtype": "Small Text",
				"insert_after": "sbi_proposal_cb",
			},
			{
				"fieldname": "sbi_design_note",
				"label": "Design Data",
				"fieldtype": "Small Text",
				"insert_after": "sbi_area_note",
			},
			{
				"fieldname": "sbi_dimensions",
				"label": "Dimensions",
				"fieldtype": "Small Text",
				"insert_after": "sbi_design_note",
			},
			{
				"fieldname": "sbi_trade_sb",
				"label": "Commercial Summary",
				"fieldtype": "Section Break",
				"insert_after": "sbi_dimensions",
			},
			{
				"fieldname": "sbi_trade_summary",
				"label": "Commercial Summary",
				"fieldtype": "Table",
				"options": "Estimation Sheet BOQ Trade",
				"insert_after": "sbi_trade_sb",
			},
			{
				"fieldname": "sbi_scope_sb",
				"label": "Scope of Works",
				"fieldtype": "Section Break",
				"insert_after": "sbi_trade_summary",
			},
			{
				"fieldname": "sbi_scope",
				"label": "Scope of Works",
				"fieldtype": "Table",
				"options": "Estimation Sheet BOQ Scope",
				"insert_after": "sbi_scope_sb",
			},
			{
				"fieldname": "sbi_delivery_note_text",
				"label": "Delivery / Completion Period",
				"fieldtype": "Small Text",
				"insert_after": "sbi_scope",
				"default": "Approximately 120-150 days from the date of work order "
				           "and receipt of advance.",
			},
		]
	}

	create_custom_fields(fields, update=True)
	frappe.db.commit()
	return len(fields["Quotation"])
