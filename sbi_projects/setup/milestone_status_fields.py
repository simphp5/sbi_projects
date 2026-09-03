# Copyright (c) 2026, Velmaska and contributors
"""Custom fields for milestone / stage billing.

Payment Schedule (child on Sales Order) gains billing + receipt status so each
stage row on the SO Terms tab shows how much has been billed and received, and
when. Sales Invoice gains a Stage field.

The base flags sbi_billed / sbi_sales_invoice are created by
milestone_custom_fields.create_milestone_custom_fields(); this module extends
that with the richer status/amount/date fields and the SI stage field.

Call create_milestone_status_fields() from after_install().
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MILESTONE_STATUS_FIELDS = {
    # -------- Payment Schedule (child on Sales Order) ------------------
    "Payment Schedule": [
        {
            "fieldname": "sbi_status",
            "label": "Billing Status",
            "fieldtype": "Select",
            "options": "\n".join(
                [
                    "",
                    "Pending",
                    "Partially Billed",
                    "Fully Billed",
                    "Partially Received",
                    "Fully Received",
                ]
            ),
            "insert_after": "sbi_sales_invoice",
            "read_only": 1,
            "allow_on_submit": 1,
            "no_copy": 1,
            "in_list_view": 1,
        },
        {
            "fieldname": "sbi_billed_amount",
            "label": "Billed Amount",
            "fieldtype": "Currency",
            "insert_after": "sbi_status",
            "read_only": 1,
            "allow_on_submit": 1,
            "no_copy": 1,
        },
        {
            "fieldname": "sbi_billed_date",
            "label": "Billed On",
            "fieldtype": "Date",
            "insert_after": "sbi_billed_amount",
            "read_only": 1,
            "allow_on_submit": 1,
            "no_copy": 1,
        },
        {
            "fieldname": "sbi_received_amount",
            "label": "Received Amount",
            "fieldtype": "Currency",
            "insert_after": "sbi_billed_date",
            "read_only": 1,
            "allow_on_submit": 1,
            "no_copy": 1,
        },
        {
            "fieldname": "sbi_received_date",
            "label": "Received On",
            "fieldtype": "Date",
            "insert_after": "sbi_received_amount",
            "read_only": 1,
            "allow_on_submit": 1,
            "no_copy": 1,
        },
    ],
    # -------- Sales Invoice -------------------------------------------
    "Sales Invoice": [
        {
            "fieldname": "sbi_stage",
            "label": "Milestone Stage",
            "fieldtype": "Data",
            "insert_after": "sbi_milestone_portion",
            "read_only": 1,
            "no_copy": 1,
        },
    ],
}


def create_milestone_status_fields():
    create_custom_fields(MILESTONE_STATUS_FIELDS, ignore_validate=True, update=True)
    frappe.db.commit()
