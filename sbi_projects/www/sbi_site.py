"""SBI Site attendance app controller (route: /sbi_site).

The single site app: face attendance, worker master, Aadhaar, shift.
Requires a signed-in user. The project comes from ?project=PROJ-xxxx.
If the user has one site it is auto-selected; if several and none is chosen,
the app shows an in-page site chooser. Guests go to the Frappe login page.
"""

import frappe

no_cache = 1

ALL_SITES_ROLES = {"System Manager", "Projects Manager", "Site Cost Approver", "Administrator"}


def get_context(context):
	context.no_header = 1
	context.no_breadcrumbs = 1

	if frappe.session.user == "Guest":
		# send to the standard Frappe login, then return here
		frappe.local.flags.redirect_location = "/login?redirect-to=/sbi_site"
		raise frappe.Redirect

	context.csrf_token = frappe.sessions.get_csrf_token()

	allowed = _allowed_projects()
	req = frappe.form_dict.get("project")

	# default: nothing chosen yet
	context.project = ""
	context.project_name = ""
	context.sites = allowed

	if req:
		if req not in [p["name"] for p in allowed]:
			frappe.throw("You do not have access to this site.", frappe.PermissionError)
		context.project = req
		context.project_name = frappe.db.get_value("Project", req, "project_name") or req
	elif len(allowed) == 1:
		context.project = allowed[0]["name"]
		context.project_name = allowed[0]["project_name"] or allowed[0]["name"]
	# else: multiple sites, none chosen -> the page shows the chooser (context.sites)

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