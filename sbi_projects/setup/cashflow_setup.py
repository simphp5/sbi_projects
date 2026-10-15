# Copyright (c) 2026, Velmaska and contributors
"""Cash Flow app for the owner: role, permissions, desktop icon, side menu. Runs on every migrate."""

import json

import frappe

ROLE = "Business Owner"
LABEL = "Cash Flow"
MODULE = "SBI Projects"
REPORTS = ("Cash Flow Summary", "Expense Split", "Profit and Loss by Period", "Project Profitability",
	"Budget vs Actual BOQ", "Site Cash Position")
SIDEBAR = [
	("Link", "Dashboard", "Page", "cash-flow", "chart-column"),
	("Section Break", "Reports", None, None, "file-text"),
] + [("Link", r, "Report", r, None) for r in REPORTS] + [
	("Section Break", "Books", None, None, "book-open"),
	("Link", "Accounts Receivable", "Report", "Accounts Receivable", None),
	("Link", "Accounts Payable", "Report", "Accounts Payable", None),
	("Link", "Profit and Loss Statement", "Report", "Profit and Loss Statement", None),
	("Section Break", "Setup", None, None, "settings"),
	("Link", "Cash Flow Settings", "DocType", "Cash Flow Settings", None),
]
ICON_FIELDS = ("label", "bg_color", "link", "link_type", "app", "icon_type", "parent_icon", "icon", "link_to",
	"idx", "standard", "logo_url", "hidden", "name", "restrict_removal", "icon_image")


def setup_cashflow():
	_role()
	_permissions()
	try:
		_sidebar_and_icon()
	except Exception:
		frappe.log_error(title="Cash Flow desktop icon")
	frappe.db.commit()


def _role():
	if not frappe.db.exists("Role", ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": ROLE, "desk_access": 1}).insert(ignore_permissions=True)


def _permissions():
	"""Reports are run 'on' Company, and the dashboard filters pick Company / Project, so the owner
	role needs to read those two."""
	from frappe.permissions import add_permission, update_permission_property

	for doctype, rights in (("Company", ("read", "report")), ("Project", ("read", "report"))):
		try:
			if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": ROLE, "permlevel": 0}):
				add_permission(doctype, ROLE, 0)
			for right in rights:
				update_permission_property(doctype, ROLE, 0, right, 1)
		except Exception:
			frappe.log_error(title="Cash Flow permission " + doctype)


def _sidebar_and_icon():
	if not frappe.db.exists("DocType", "Desktop Icon"):
		return
	use_sidebar = frappe.db.exists("DocType", "Workspace Sidebar") and \
		frappe.get_meta("Workspace Sidebar").has_field("items")
	if use_sidebar:
		_sidebar()

	meta = frappe.get_meta("Desktop Icon")
	if frappe.db.exists("Desktop Icon", LABEL):
		doc = frappe.get_doc("Desktop Icon", LABEL)
	else:
		doc = frappe.new_doc("Desktop Icon")
		top = frappe.get_all("Desktop Icon", filters={"parent_icon": ["in", ["", None]]}, pluck="idx")
		doc.idx = max([i or 0 for i in top] or [0]) + 1
	values = {"label": LABEL, "icon_type": "Link", "parent_icon": None, "icon": "wallet", "app": "sbi_projects",
		"standard": 0, "hidden": 0, "bg_color": "blue"}
	if use_sidebar:
		values.update(link_type="Workspace Sidebar", link_to=LABEL, link=None)
	else:
		values.update(link_type="External", link="/app/cash-flow")
	for field, value in values.items():
		if meta.has_field(field):
			doc.set(field, value)
	if meta.has_field("roles"):
		doc.set("roles", [{"role": ROLE}])
	doc.flags.ignore_links = True
	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	doc.save(ignore_permissions=True)
	_add_to_saved_layouts(doc)


def _sidebar():
	if frappe.db.exists("Workspace Sidebar", LABEL):
		side = frappe.get_doc("Workspace Sidebar", LABEL)
	else:
		side = frappe.new_doc("Workspace Sidebar")
		side.title = LABEL
	for field, value in (("header_icon", "wallet"), ("module", MODULE), ("app", "sbi_projects"), ("standard", 0)):
		if side.meta.has_field(field):
			side.set(field, value)
	side.set("items", [])
	for row_type, label, link_type, link_to, icon in SIDEBAR:
		if link_type and not frappe.db.exists(link_type, link_to):
			continue
		row = {"type": row_type, "label": label, "icon": icon, "collapsible": 1,
			"child": 1 if row_type == "Link" and link_type != "Page" else 0,
			"indent": 1 if row_type == "Section Break" else 0}
		if link_type:
			row.update(link_type=link_type, link_to=link_to)
		side.append("items", row)
	side.flags.ignore_links = True
	side.flags.ignore_permissions = True
	side.save(ignore_permissions=True)


def _add_to_saved_layouts(icon):
	"""Users who once arranged their desktop see their saved copy, not the live icon list."""
	if not frappe.db.exists("DocType", "Desktop Layout"):
		return
	owners = set(frappe.get_all("Has Role", filters={"parenttype": "User", "role": ROLE}, pluck="parent"))
	owners.add("Administrator")
	row = {f: icon.get(f) for f in ICON_FIELDS if icon.meta.has_field(f) or f == "name"}
	for name in frappe.get_all("Desktop Layout", pluck="name"):
		raw = frappe.db.get_value("Desktop Layout", name, "layout")
		try:
			layout = json.loads(raw) if raw else None
		except Exception:
			continue
		if not isinstance(layout, list):
			continue
		kept = [i for i in layout if not (isinstance(i, dict) and i.get("label") == LABEL)]
		if name in owners:
			kept.append(dict(row, child_icons=[]))
		if len(kept) != len(layout) or name in owners:
			frappe.db.set_value("Desktop Layout", name, "layout", json.dumps(kept), update_modified=False)
	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")
