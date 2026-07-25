# Copyright (c) 2026, Velmaska and contributors
"""Custom field: a read-only mapped-project caption on the Sales Order.

Rendered entirely by sales_order.js (reverse lookup of Project.sales_order),
so this is just an HTML placeholder positioned under Delivery Date.

Call create_so_project_field() from after_install().
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

SO_PROJECT_FIELD = {
    "Sales Order": [
        {
            "fieldname": "sbi_mapped_project",
            "label": "Project",
            "fieldtype": "HTML",
            "insert_after": "delivery_date",
            "read_only": 1,
            "no_copy": 1,
            "print_hide": 1,
        },
    ],
}


def create_so_project_field():
    create_custom_fields(SO_PROJECT_FIELD, ignore_validate=True, update=True)
    frappe.db.commit()
