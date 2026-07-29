import json

import frappe
import frappe.sessions


def get_context(context):
    context.no_cache = 1
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = \
            "/login?redirect-to=/sbi_ops"
        raise frappe.Redirect
    project = frappe.form_dict.get("project") or ""
    context.project = project
    context.csrf_token = frappe.sessions.get_csrf_token()
    # site chooser data: projects where user has access
    projects = frappe.get_all("Project",
                              filters={"status": "Open"},
                              fields=["name", "project_name"],
                              order_by="modified desc",
                              limit_page_length=20)
    context.projects_json = json.dumps([[p.name, p.project_name or p.name]
                                        for p in projects])
    return context
