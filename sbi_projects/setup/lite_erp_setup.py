# Copyright (c) 2026, Velmaska and contributors
"""Keep the Lite ERP and SBI Office desktop icons and the Lite ERP workspace on every migrate.

Lite ERP itself (page, API, punch app) is installed from System Console (lite_erp/dist). Those icons
and the workspace are site records with no file in this app, so a migrate's orphan clean-up removes
them. This step puts them back after every migrate. It never changes the page or the API scripts.
"""

import json

import frappe

LITE = "Lite ERP"
LITE_ROUTE = "/desk/lite-erp"
OFFICE = "SBI Office"
OFFICE_ROUTE = "/sbi_office"
LITE_ROLES = ("System Manager", "Accounts Manager", "Accounts User", "Business Owner", "HR Manager", "HR User",
	"SBI Staff", "Employee", "Employee Self Service", "Sales User", "Sales Manager", "Purchase User",
	"Purchase Manager", "Projects User", "Projects Manager")
OFFICE_ROLES = ("Employee", "Employee Self Service", "HR Manager", "HR User", "System Manager", "Business Owner",
	"Accounts Manager", "Accounts User")
ICON_FIELDS = ("label", "bg_color", "link", "link_type", "app", "icon_type", "parent_icon", "icon", "link_to",
	"idx", "standard", "logo_url", "hidden", "name", "restrict_removal", "icon_image")


def setup_lite_erp():
	# Lite ERP was never installed on this site: nothing to keep
	if not frappe.db.exists("Server Script", "SBI Lite ERP"):
		return
	_workspace()
	if frappe.db.exists("DocType", "Desktop Icon"):
		_icon(LITE, LITE_ROUTE, "layout", LITE_ROLES)
		if frappe.db.exists("Web Page", {"route": "sbi_office"}):
			_icon(OFFICE, OFFICE_ROUTE, "map-pin", OFFICE_ROLES)
		frappe.cache.delete_key("desktop_icons")
		frappe.cache.delete_key("bootinfo")
	frappe.db.commit()


def _roles(wanted):
	return [r for r in wanted if frappe.db.exists("Role", r)]


def _workspace():
	if frappe.db.exists("Workspace", LITE):
		ws = frappe.get_doc("Workspace", LITE)
		if not ws.standard and ws.custom_blocks:
			return
	else:
		ws = frappe.new_doc("Workspace")
		ws.label = LITE
	ws.title = LITE
	ws.module = "SBI Projects" if frappe.db.exists("Module Def", "SBI Projects") else "Accounts"
	ws.public = 1
	ws.is_hidden = 0
	ws.standard = 0
	ws.type = "Workspace"
	ws.icon = "layout"
	ws.sequence_id = 0.5
	if frappe.db.exists("Custom HTML Block", LITE):
		ws.content = json.dumps([{"id": "sbiLiteErp01", "type": "custom_block", "data": {"custom_block_name": LITE, "col": 12}}])
		ws.set("custom_blocks", [{"custom_block_name": LITE, "label": LITE}])
	ws.set("shortcuts", [])
	ws.set("roles", [{"role": r} for r in _roles(LITE_ROLES)])
	ws.flags.ignore_links = True
	ws.flags.ignore_permissions = True
	ws.save(ignore_permissions=True)


def _icon(label, route, icon_name, wanted_roles):
	meta = frappe.get_meta("Desktop Icon")
	if frappe.db.exists("Desktop Icon", label):
		doc = frappe.get_doc("Desktop Icon", label)
	else:
		doc = frappe.new_doc("Desktop Icon")
		top = frappe.get_all("Desktop Icon", filters={"parent_icon": ["in", ["", None]]}, pluck="idx")
		doc.idx = max([i or 0 for i in top] or [0]) + 1
	values = {"label": label, "icon_type": "App", "link_type": "External", "link": route, "link_to": None,
		"icon": icon_name, "bg_color": "blue", "app": "sbi_projects", "standard": 1, "hidden": 0, "parent_icon": None}
	for field, value in values.items():
		if meta.has_field(field):
			doc.set(field, value)
	roles = _roles(wanted_roles)
	if meta.has_field("roles"):
		doc.set("roles", [{"role": r} for r in roles])
	doc.flags.ignore_links = True
	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	doc.save(ignore_permissions=True)
	# a non-Administrator owner hides an App icon from everyone else
	frappe.db.set_value("Desktop Icon", doc.name, "owner", "Administrator", update_modified=False)
	_add_to_saved_layouts(doc, roles)


def _add_to_saved_layouts(icon, roles):
	"""Users who once arranged their desktop see their saved copy, not the live icon list."""
	if not frappe.db.exists("DocType", "Desktop Layout"):
		return
	users = {"Administrator"}
	if roles:
		users.update(frappe.get_all("Has Role", filters={"parenttype": "User", "role": ["in", roles]}, pluck="parent"))
	row = {f: icon.get(f) for f in ICON_FIELDS if icon.meta.has_field(f) or f == "name"}
	for name in frappe.get_all("Desktop Layout", pluck="name"):
		if name not in users:
			continue
		raw = frappe.db.get_value("Desktop Layout", name, "layout")
		try:
			layout = json.loads(raw) if raw else None
		except Exception:
			continue
		if not isinstance(layout, list):
			continue
		if any(isinstance(i, dict) and i.get("label") == icon.label for i in layout):
			continue
		layout.append(dict(row, child_icons=[]))
		frappe.db.set_value("Desktop Layout", name, "layout", json.dumps(layout), update_modified=False)
