"""Set up a login for a site in-charge from the Project form.

Site staff usually have no email, so a login cannot be auto-created silently
(there is nowhere to send a password).  Instead the owner assigns the in-charge
on the project, then uses one button: it creates a System User with a chosen
password, gives it the Projects User role, and records a Site Assignment so the
site app shows that person only their own site.
"""

import frappe
from frappe.utils import today


PROJECT_ROLE = "Projects User"


@frappe.whitelist()
def get_incharge_login_status(project):
	"""What login state the project's in-charge is in, for the form panel."""
	incharge = frappe.db.get_value("Project", project, "sbi_site_incharge")
	if not incharge:
		return {"has_incharge": False}

	emp = frappe.db.get_value(
		"Employee", incharge,
		["employee_name", "user_id", "company_email", "personal_email"],
		as_dict=True,
	) or {}

	user_id = emp.get("user_id")
	assigned = frappe.db.exists(
		"Site Assignment",
		{"project": project, "employee": incharge, "status": "Open"},
	)

	return {
		"has_incharge": True,
		"employee": incharge,
		"employee_name": emp.get("employee_name"),
		"has_login": bool(user_id),
		"user_id": user_id,
		"has_assignment": bool(assigned),
		"suggested_username": _suggest_username(incharge, emp.get("employee_name")),
	}


def _suggest_username(employee, name):
	base = (name or employee or "site").strip().lower()
	base = "".join(ch if ch.isalnum() else "." for ch in base)
	base = ".".join(p for p in base.split(".") if p)
	return (base or "site") + "@shiv-bharat.local"


@frappe.whitelist()
def setup_incharge_login(project, username=None, password=None):
	"""Create (or link) a login for the project's in-charge and assign the site.

	Idempotent: if the in-charge already has a user, we reuse it and just make
	sure the role and the Site Assignment are in place.
	"""
	incharge = frappe.db.get_value("Project", project, "sbi_site_incharge")
	if not incharge:
		frappe.throw("Assign a site in-charge on the project first.")

	emp = frappe.get_doc("Employee", incharge)
	user_id = emp.user_id

	# 1. user
	if not user_id:
		if not username:
			frappe.throw("Enter a username for the login.")
		if not password:
			frappe.throw("Enter a password for the login.")
		if frappe.db.exists("User", username):
			frappe.throw("That username already exists. Choose another.")

		user = frappe.get_doc({
			"doctype": "User",
			"email": username,
			"first_name": emp.employee_name or incharge,
			"user_type": "System User",
			"send_welcome_email": 0,
			"new_password": password,
		})
		user.insert(ignore_permissions=True)
		user_id = user.name

		emp.user_id = user_id
		emp.save(ignore_permissions=True)
	else:
		user = frappe.get_doc("User", user_id)

	# 2. role
	existing_roles = {r.role for r in user.roles}
	if PROJECT_ROLE not in existing_roles:
		user.append("roles", {"role": PROJECT_ROLE})
		user.save(ignore_permissions=True)

	# 3. site assignment (so the app filters to this site)
	if not frappe.db.exists("Site Assignment",
	                        {"project": project, "employee": incharge, "status": "Open"}):
		frappe.get_doc({
			"doctype": "Site Assignment",
			"project": project,
			"employee": incharge,
			"role": "Site In-charge",
			"from_date": today(),
			"status": "Open",
		}).insert(ignore_permissions=True)

	frappe.db.commit()
	return {"user_id": user_id, "done": True}