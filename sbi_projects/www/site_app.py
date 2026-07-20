import frappe

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.throw("Please sign in to use the site app.", frappe.PermissionError)

	context.no_header = 1
	context.csrf_token = frappe.sessions.get_csrf_token()
	context.user_fullname = frappe.utils.get_fullname(frappe.session.user)
	context.projects = frappe.get_all(
		"Project",
		filters={"status": "Open"},
		fields=["name", "project_name"],
		order_by="project_name asc",
		limit_page_length=200,
	)
	return context