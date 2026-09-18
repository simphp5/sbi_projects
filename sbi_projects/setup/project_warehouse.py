import frappe

PARENT_GROUP = "Site Stores"
PROJECT_FIELD = "sbi_warehouse"


def _abbr(company):
	return frappe.db.get_value("Company", company, "abbr") or ""


def _company_for(doc):
	company = doc.get("company")
	if company:
		return company
	return frappe.defaults.get_user_default("Company") or frappe.db.get_value(
		"Company", {}, "name"
	)


def ensure_parent_group(company):
	"""Create the 'Site Stores' group warehouse once per company."""
	abbr = _abbr(company)
	name = "%s - %s" % (PARENT_GROUP, abbr)
	if frappe.db.exists("Warehouse", name):
		return name

	root = frappe.db.get_value(
		"Warehouse",
		{"company": company, "is_group": 1, "parent_warehouse": ["in", ["", None]]},
		"name",
	)
	if not root:
		root = frappe.db.get_value("Warehouse", {"company": company, "is_group": 1}, "name")

	doc = frappe.new_doc("Warehouse")
	doc.warehouse_name = PARENT_GROUP
	doc.company = company
	doc.is_group = 1
	if root:
		doc.parent_warehouse = root
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	return doc.name


def create_project_warehouse(project_doc):
	"""Return the warehouse name for this project, creating it if needed."""
	company = _company_for(project_doc)
	if not company:
		return None

	title = (project_doc.get("project_name") or project_doc.name or "").strip()
	if not title:
		return None

	abbr = _abbr(company)
	expected = "%s - %s" % (title, abbr)

	existing = project_doc.get(PROJECT_FIELD)
	if existing and frappe.db.exists("Warehouse", existing):
		if existing != expected and not frappe.db.exists("Warehouse", expected):
			try:
				frappe.rename_doc("Warehouse", existing, expected, force=True)
				return expected
			except Exception:
				frappe.log_error(frappe.get_traceback(), "SBI: warehouse rename failed")
		return existing

	if frappe.db.exists("Warehouse", expected):
		return expected

	parent = ensure_parent_group(company)
	doc = frappe.new_doc("Warehouse")
	doc.warehouse_name = title
	doc.company = company
	doc.is_group = 0
	if parent:
		doc.parent_warehouse = parent
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	return doc.name


def project_after_insert(doc, method=None):
	_sync(doc)


def project_on_update(doc, method=None):
	_sync(doc)


def _sync(doc):
	if not doc.meta.has_field(PROJECT_FIELD):
		return
	try:
		warehouse = create_project_warehouse(doc)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "SBI: project warehouse")
		return

	if warehouse and doc.get(PROJECT_FIELD) != warehouse:
		frappe.db.set_value("Project", doc.name, PROJECT_FIELD, warehouse, update_modified=False)
		doc.set(PROJECT_FIELD, warehouse)


@frappe.whitelist()
def warehouse_for_project(project):
	"""Used by the purchase forms to default the store."""
	if not project:
		return None
	warehouse = frappe.db.get_value("Project", project, PROJECT_FIELD)
	if warehouse and frappe.db.exists("Warehouse", warehouse):
		return warehouse

	doc = frappe.get_doc("Project", project)
	doc.check_permission("read")
	return create_project_warehouse(doc)


@frappe.whitelist()
def backfill_project_warehouses(dry_run=0):
	"""Create a store for every existing project that has none."""
	frappe.only_for("System Manager")

	names = frappe.get_all("Project", pluck="name", limit_page_length=0)
	created = []
	skipped = []

	for name in names:
		doc = frappe.get_doc("Project", name)
		if doc.get(PROJECT_FIELD) and frappe.db.exists("Warehouse", doc.get(PROJECT_FIELD)):
			skipped.append({"project": name, "warehouse": doc.get(PROJECT_FIELD)})
			continue
		if int(dry_run or 0):
			created.append({"project": name, "warehouse": "(would create)"})
			continue
		try:
			warehouse = create_project_warehouse(doc)
			if warehouse:
				frappe.db.set_value(
					"Project", name, PROJECT_FIELD, warehouse, update_modified=False
				)
				created.append({"project": name, "warehouse": warehouse})
		except Exception:
			frappe.log_error(frappe.get_traceback(), "SBI: backfill warehouse " + name)

	if not int(dry_run or 0):
		frappe.db.commit()

	return {
		"projects": len(names),
		"created": len(created),
		"created_list": created[:50],
		"already_had_one": len(skipped),
		"dry_run": bool(int(dry_run or 0)),
	}


# ---------------------------------------------------------------- validation


def _site_store_map(company):
	"""warehouse -> project, for warehouses that are project site stores."""
	rows = frappe.get_all(
		"Project",
		filters={PROJECT_FIELD: ["is", "set"]},
		fields=["name", "project_name", PROJECT_FIELD],
		limit_page_length=0,
	)
	return {
		r.get(PROJECT_FIELD): {"project": r.name, "label": r.project_name or r.name}
		for r in rows
		if r.get(PROJECT_FIELD)
	}


def check_row_warehouse(doc, method=None):
	"""Block a row whose warehouse is another project's site store."""
	rows = doc.get("items") or []
	if not rows:
		return

	store_map = None
	for row in rows:
		project = row.get("project") or row.get("sbi_project") or doc.get("project")
		warehouse = row.get("warehouse") or row.get("t_warehouse")
		if not project or not warehouse:
			continue

		if store_map is None:
			store_map = _site_store_map(doc.get("company"))

		owner = store_map.get(warehouse)
		if not owner:
			# not a project site store (central store, transit, etc.) - allowed
			continue
		if owner["project"] == project:
			continue

		expected = frappe.db.get_value("Project", project, PROJECT_FIELD)
		project_label = frappe.db.get_value("Project", project, "project_name") or project

		frappe.throw(
			frappe._(
				"Row {0}: warehouse <b>{1}</b> is the site store of <b>{2}</b>, "
				"but this row is booked to project <b>{3}</b>.<br><br>"
				"Use <b>{4}</b>, or run <b>Tools &gt; Set Store from Project</b>."
			).format(
				row.idx,
				frappe.utils.escape_html(warehouse),
				frappe.utils.escape_html(owner["label"]),
				frappe.utils.escape_html(project_label),
				frappe.utils.escape_html(expected or "the project's own store"),
			),
			title=frappe._("Wrong Site Store"),
		)
