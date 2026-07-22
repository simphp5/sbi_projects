import frappe

no_cache = 1

# Roles that may work on any site.  Everyone else sees only the sites they are
# assigned to, so a site engineer on a shared tablet cannot record attendance
# against another team's project.
ALL_SITES_ROLES = {
	"System Manager",
	"Projects Manager",
	"Site Cost Approver",
	"Administrator",
}


def get_context(context):
	context.no_header = 1
	context.csrf_token = frappe.sessions.get_csrf_token()

	# Not signed in: render the app, which shows its own login screen.
	if frappe.session.user == "Guest":
		context.projects = None
		context.projects_json = "null"
		return context

	projects = get_allowed_projects()
	context.user_fullname = frappe.utils.get_fullname(frappe.session.user)
	context.projects = projects
	context.projects_json = frappe.as_json(projects)
	return context


def get_allowed_projects():
	if can_see_all_sites():
		return open_projects()
	names = assigned_projects(frappe.session.user)
	if not names:
		return []
	return open_projects(names)


def can_see_all_sites():
	if frappe.session.user == "Administrator":
		return True
	return bool(ALL_SITES_ROLES & set(frappe.get_roles()))


def assigned_projects(user):
	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not employee:
		return []
	rows = frappe.get_all(
		"Site Assignment",
		filters={"employee": employee, "to_date": ("is", "not set")},
		pluck="project",
	)
	meta = frappe.get_meta("Project")
	for field in ("sbi_site_incharge", "sbi_storekeeper",
	              "custom_site_incharge", "custom_site_storekeeper"):
		if meta.has_field(field):
			rows += frappe.get_all("Project", filters={field: employee}, pluck="name")
	return list(set(rows))


def open_projects(names=None):
	filters = {"status": "Open"}
	if names is not None:
		filters["name"] = ("in", names)
	return frappe.get_all(
		"Project",
		filters=filters,
		fields=["name", "project_name"],
		order_by="project_name asc",
		limit_page_length=200,
	)