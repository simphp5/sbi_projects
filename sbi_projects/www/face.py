"""Standalone face-attendance page controller.

Requires a signed-in user with access to the site.  The project comes from the
URL (?project=PROJ-xxxx); if the user has exactly one assigned site and none is
given, that one is used.  Everything else (login, chooser) stays in /site_app.
"""

import frappe

no_cache = 1

ALL_SITES_ROLES = {"System Manager", "Projects Manager", "Site Cost Approver", "Administrator"}


def get_context(context):
	context.no_header = 1
	context.no_breadcrumbs = 1

	if frappe.session.user == "Guest":
		# send them to the main app to sign in, then come back
		frappe.local.flags.redirect_location = "/site_app"
		raise frappe.Redirect

	context.csrf_token = frappe.sessions.get_csrf_token()

	allowed = _allowed_projects()
	req = frappe.form_dict.get("project")

	if req:
		if req not in [p["name"] for p in allowed]:
			frappe.throw("You do not have access to this site.", frappe.PermissionError)
		project = req
	elif len(allowed) == 1:
		project = allowed[0]["name"]
	else:
		# no project chosen and more than one available -> back to the chooser
		frappe.local.flags.redirect_location = "/site_app"
		raise frappe.Redirect

	context.project = project
	context.project_name = frappe.db.get_value("Project", project, "project_name") or project
	return context


def _allowed_projects():
	if frappe.session.user == "Administrator" or (ALL_SITES_ROLES & set(frappe.get_roles())):
		return frappe.get_all("Project", filters={"status": "Open"},
			fields=["name", "project_name"], order_by="project_name asc", limit_page_length=200)

	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	names = []
	if employee:
		names += frappe.get_all("Site Assignment", filters={"employee": employee}, pluck="project")
		meta = frappe.get_meta("Project")
		for f in ("sbi_site_incharge", "sbi_storekeeper"):
			if meta.has_field(f):
				names += frappe.get_all("Project", filters={f: employee}, pluck="name")
	names = list(set(n for n in names if n))
	if not names:
		return []
	return frappe.get_all("Project", filters={"status": "Open", "name": ("in", names)},
		fields=["name", "project_name"], order_by="project_name asc")