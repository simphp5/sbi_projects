import json

import frappe
from sbi_projects.project_cost_api import build_customer_view


def get_context(context):
    context.no_cache = 1
    token = frappe.form_dict.get("token") or ""
    data = build_customer_view(token) if token else None
    context.valid = 1 if data else 0
    context.data_json = json.dumps(data)
    return context
