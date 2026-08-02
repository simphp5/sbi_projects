import json

import frappe
import frappe.sessions
from sbi_projects.project_cost_api import OWNER_ROLES, get_cost_overview


def get_context(context):
    context.no_cache = 1
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/sbi_owner"
        raise frappe.Redirect
    roles = set(frappe.get_roles())
    if not roles.intersection(set(OWNER_ROLES)):
        frappe.throw("Not permitted", frappe.PermissionError)
    project = frappe.form_dict.get("project") or ""
    context.project = project
    context.csrf_token = frappe.sessions.get_csrf_token()
    data = None
    if project:
        data = get_cost_overview(project)
    context.data_json = json.dumps(data)
    projects = frappe.get_all("Project", filters={"status": "Open"},
                              fields=["name", "project_name"],
                              order_by="modified desc", limit_page_length=30)
    context.projects_json = json.dumps(
        [[p.name, p.project_name or p.name] for p in projects])
    return context
