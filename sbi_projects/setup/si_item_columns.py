# Copyright (c) 2026, Velmaska and contributors
"""Milestone display columns on the Sales Invoice Item child table.

These are reference columns filled by milestone billing so the invoice line
shows which project / stage / payment term it bills, the stage percentage, and
the SO line's GST-inclusive value. They are display-only and never affect the
invoice's own totals or GST (which come from the item rate + tax template).

Call create_si_item_columns() from after_install().
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

SI_ITEM_COLUMNS = {
    "Sales Invoice Item": [
        {
            "fieldname": "sbi_project",
            "label": "Project",
            "fieldtype": "Link",
            "options": "Project",
            "insert_after": "cost_center",
            "read_only": 1,
            "in_list_view": 0,
        },
        {
            "fieldname": "sbi_stage",
            "label": "Stage",
            "fieldtype": "Data",
            "insert_after": "sbi_project",
            "read_only": 1,
            "in_list_view": 1,
            "columns": 2,
        },
        {
            "fieldname": "sbi_payment_term",
            "label": "Payment Term",
            "fieldtype": "Data",
            "insert_after": "sbi_stage",
            "read_only": 1,
        },
        {
            "fieldname": "sbi_invoice_portion",
            "label": "Invoice Portion (%)",
            "fieldtype": "Percent",
            "insert_after": "sbi_payment_term",
            "read_only": 1,
            "in_list_view": 1,
            "columns": 1,
        },
        {
            "fieldname": "sbi_total_excl_gst",
            "label": "SO Value excl GST",
            "fieldtype": "Currency",
            "insert_after": "sbi_invoice_portion",
            "read_only": 1,
            "description": "Full Sales Order line value excluding GST (reference only)",
        },
        {
            "fieldname": "sbi_total_incl_gst",
            "label": "SO Value incl GST",
            "fieldtype": "Currency",
            "insert_after": "sbi_total_excl_gst",
            "read_only": 1,
            "description": "Full Sales Order line value including GST (reference only)",
        },
    ],
}


def create_si_item_columns():
    create_custom_fields(SI_ITEM_COLUMNS, ignore_validate=True, update=True)
    frappe.db.commit()
