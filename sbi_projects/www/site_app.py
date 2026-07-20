import frappe

no_cache = 1

# Roles that may work on any site.  Everyone else sees only the sites they are
# currently assigned to, so a site engineer opening the app on a shared tablet
# cannot record attendance against somebody else's project.
ALL_SITES_ROLES = {
	"System Manager",
	"Projects Manager",
	"Site Cost Approver",
	"Administrator",
}


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.throw("Please sign in to use the site app.", frappe.PermissionError)

	projects = get_allowed_projects()

	context.no_header = 1
	context.csrf_token = frappe.sessions.get_csrf_token()
	context.user_fullname = frappe.utils.get_fullname(frappe.session.user)
	context.projects = projects
	# Serialise here: frappe.as_json is not exposed inside the Jinja sandbox.
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
	"""Projects where this user currently holds an open site assignment."""
	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not employee:
		return []

	rows = frappe.get_all(
		"Site Assignment",
		filters={"employee": employee, "to_date": ("is", "not set")},
		pluck="project",
	)

	# Fall back to whoever is named directly on the project, in case a site was
	# set up before Site Assignment records were being kept.
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