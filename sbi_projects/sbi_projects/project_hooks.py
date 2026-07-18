# Copyright (c) 2026, Velmaska and contributors
"""Stage generation for Projects.

Two sources, in priority order:
  1. Sales Order payment schedule  -> each payment milestone becomes a stage
  2. SBI Project Template          -> each template row becomes a stage

Each stage becomes a *group* Task (is_group = 1) so the user can nest
sub-tasks under it as a tree.
"""

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, nowdate


# ------------------------------------------------------------------
# Hooked on Project.after_insert
# ------------------------------------------------------------------
def build_project_stages(doc, method=None):
	if frappe.db.exists("Task", {"project": doc.name}):
		return

	if doc.get("sales_order"):
		created = create_stages_from_sales_order(doc.name)
		if created:
			return

	if doc.get("sbi_project_template"):
		create_stages_from_template(doc.name)


# ==================================================================
# 1. SALES ORDER  ->  STAGES
# ==================================================================
@frappe.whitelist()
def create_stages_from_sales_order(project):
	"""Read the linked SO's payment schedule and create one group Task per row.

	invoice_portion  -> task_weight   (so % complete tracks billing milestones)
	payment_amount   -> sbi_stage_budget
	due_date         -> exp_end_date
	"""
	prj = frappe.get_doc("Project", project)
	if not prj.sales_order:
		frappe.throw(_("This project is not linked to a Sales Order"))

	so = frappe.get_doc("Sales Order", prj.sales_order)
	if not so.payment_schedule:
		frappe.msgprint(
			_("Sales Order {0} has no Payment Schedule. Add payment terms first.").format(so.name),
			indicator="orange",
			alert=True,
		)
		return 0

	start = getdate(prj.expected_start_date or so.transaction_date or nowdate())
	previous_task = None
	count = 0

	for row in so.payment_schedule:
		stage = row.get("sbi_stage")
		subject = stage or row.get("description") or row.get("payment_term") or f"Milestone {row.idx}"

		task = frappe.new_doc("Task")
		task.subject = subject
		task.project = project
		task.status = "Open"
		task.is_group = 1  # allows sub-tasks -> tree structure
		task.task_weight = flt(row.invoice_portion)
		task.exp_start_date = start if row.idx == 1 else None
		task.exp_end_date = row.due_date
		task.description = row.get("description") or ""

		if stage:
			task.sbi_stage = stage
		task.sbi_stage_budget = flt(row.payment_amount)
		task.sbi_invoice_portion = flt(row.invoice_portion)
		task.sbi_payment_term = row.get("payment_term")

		if previous_task:
			task.append("depends_on", {"task": previous_task})

		task.insert(ignore_permissions=True)
		previous_task = task.name
		count += 1

	# contract value + estimate from the SO
	frappe.db.set_value("Project", project, {
		"sbi_contract_value": flt(so.rounded_total or so.grand_total),
		"percent_complete_method": "Task Weight",
	})

	frappe.msgprint(
		_("{0} stages created from Sales Order {1}").format(count, so.name),
		indicator="green",
		alert=True,
	)
	return count


# ==================================================================
# 2. SBI PROJECT TEMPLATE  ->  STAGES
# ==================================================================
@frappe.whitelist()
def create_stages_from_template(project):
	prj = frappe.get_doc("Project", project)
	if not prj.sbi_project_template:
		frappe.throw(_("No Project Template selected"))

	template = frappe.get_doc("SBI Project Template", prj.sbi_project_template)
	start = getdate(prj.expected_start_date or nowdate())

	stage_to_task = {}
	cursor = start
	count = 0

	for row in template.stages:
		exp_start = cursor
		duration = int(row.duration_days or 1)
		exp_end = add_days(exp_start, max(duration - 1, 0))

		task = frappe.new_doc("Task")
		task.subject = row.stage
		task.project = project
		task.status = "Open"
		task.is_group = 1  # tree parent
		task.task_weight = flt(row.weight)
		task.exp_start_date = exp_start
		task.exp_end_date = exp_end
		task.is_milestone = row.is_milestone or 0
		task.description = row.stage_description or ""
		task.sbi_stage = row.stage

		if row.depends_on_stage and stage_to_task.get(row.depends_on_stage):
			task.append("depends_on", {"task": stage_to_task[row.depends_on_stage]})

		task.insert(ignore_permissions=True)
		stage_to_task[row.stage] = task.name
		cursor = add_days(exp_end, 1)
		count += 1

	frappe.db.set_value("Project", project, "percent_complete_method", "Task Weight")
	frappe.msgprint(
		_("{0} stages created from template {1}").format(count, template.name),
		indicator="green",
		alert=True,
	)
	return count


# ==================================================================
# 3. STAGE BUDGET vs ACTUAL  (BOQ + purchases, rolled up by stage)
# ==================================================================
@frappe.whitelist()
def get_stage_summary(project):
	"""Per-stage: budget (from SO payment schedule), BOQ estimate, and actual cost."""
	tasks = frappe.get_all(
		"Task",
		filters={"project": project, "is_group": 1},
		fields=[
			"name", "subject", "sbi_stage", "task_weight",
			"sbi_stage_budget", "progress", "status",
			"exp_end_date", "total_costing_amount",
		],
		order_by="exp_end_date asc, creation asc",
	)

	# BOQ estimate per stage (submitted BOQs only)
	boq_rows = frappe.db.sql(
		"""
		SELECT bi.stage, SUM(bi.amount) AS amount
		FROM `tabBOQ Item` bi
		INNER JOIN `tabBOQ` b ON b.name = bi.parent
		WHERE b.project = %s AND b.docstatus = 1
		GROUP BY bi.stage
		""",
		project,
		as_dict=True,
	)
	boq_by_stage = {r.stage: flt(r.amount) for r in boq_rows if r.stage}

	out = []
	for t in tasks:
		budget = flt(t.sbi_stage_budget)
		boq = flt(boq_by_stage.get(t.sbi_stage))
		actual = flt(t.total_costing_amount)
		out.append({
			"task": t.name,
			"stage": t.sbi_stage or t.subject,
			"weight": flt(t.task_weight),
			"due_date": t.exp_end_date,
			"budget": budget,
			"boq_estimate": boq,
			"actual": actual,
			"variance": budget - boq,
			"progress": flt(t.progress),
			"status": t.status,
		})
	return out


# ---------------------------------------------------------------------------
# Site masters: auto-create Cost Center + Warehouse for every Project (= Site)
# ---------------------------------------------------------------------------

def create_site_masters(doc, method=None):
    """Project.after_insert -- provision site Cost Center and Warehouse.

    Never raises: a failure here must not block Project creation.
    Idempotent: safe to re-run on any Project.
    """
    try:
        _provision_site_masters(doc)
    except Exception:
        frappe.log_error(
            title="create_site_masters failed: {0}".format(doc.name),
            message=frappe.get_traceback(),
        )
        frappe.msgprint(
            "Site Cost Center / Warehouse could not be created automatically. "
            "The project was saved.",
            title="Site Setup Incomplete",
            indicator="orange",
        )


def _provision_site_masters(doc):
    company = doc.company or frappe.defaults.get_user_default("Company")
    if not company:
        return

    abbr = frappe.get_cached_value("Company", company, "abbr")
    label = (doc.project_name or doc.name).strip()[:120]

    cc = _ensure_site_cost_center(company, abbr, label)
    wh = _ensure_site_warehouse(company, abbr, label)

    _set_if_field_exists(doc, "custom_site_cost_center", cc)
    _set_if_field_exists(doc, "custom_site_warehouse", wh)
    if not doc.get("cost_center"):
        _set_if_field_exists(doc, "cost_center", cc)


def _ensure_site_cost_center(company, abbr, label):
    """Create '<label> - <abbr>' under a 'Sites - <abbr>' group."""
    target = "{0} - {1}".format(label, abbr)
    if frappe.db.exists("Cost Center", target):
        return target

    parent = _ensure_sites_cc_group(company, abbr)
    cc = frappe.get_doc({
        "doctype": "Cost Center",
        "cost_center_name": label,
        "company": company,
        "parent_cost_center": parent,
        "is_group": 0,
    }).insert(ignore_permissions=True)
    return cc.name


def _ensure_sites_cc_group(company, abbr):
    group = "Sites - {0}".format(abbr)
    if frappe.db.exists("Cost Center", group):
        return group

    root = frappe.db.get_value(
        "Cost Center",
        {"company": company, "is_group": 1,
         "parent_cost_center": ("in", ("", None))},
        "name",
    ) or frappe.db.get_value(
        "Cost Center", {"company": company, "is_group": 1}, "name"
    )
    if not root:
        frappe.throw("No group Cost Center found for company {0}".format(company))

    doc = frappe.get_doc({
        "doctype": "Cost Center",
        "cost_center_name": "Sites",
        "company": company,
        "parent_cost_center": root,
        "is_group": 1,
    }).insert(ignore_permissions=True)
    return doc.name


def _ensure_site_warehouse(company, abbr, label):
    target = "{0} - {1}".format(label, abbr)
    if frappe.db.exists("Warehouse", target):
        return target

    conventional = "All Warehouses - {0}".format(abbr)
    parent = conventional if frappe.db.exists("Warehouse", conventional) else \
        frappe.db.get_value(
            "Warehouse",
            {"company": company, "is_group": 1,
             "parent_warehouse": ("in", ("", None))},
            "name",
        )

    wh = frappe.get_doc({
        "doctype": "Warehouse",
        "warehouse_name": label,
        "company": company,
        "parent_warehouse": parent,
        "is_group": 0,
    }).insert(ignore_permissions=True)
    return wh.name


def _set_if_field_exists(doc, fieldname, value):
    """Write only if the field actually exists on Project -- avoids errors
    when custom fields have not been installed yet."""
    if not value:
        return
    if not doc.meta.has_field(fieldname):
        return
    doc.db_set(fieldname, value, update_modified=False)


@frappe.whitelist()
def backfill_site_masters(project=None):
    """Repair Projects created while this hook was broken."""
    frappe.only_for("System Manager")
    names = [project] if project else frappe.get_all("Project", pluck="name")
    ok, failed = [], []
    for name in names:
        try:
            _provision_site_masters(frappe.get_doc("Project", name))
            ok.append(name)
        except Exception:
            failed.append(name)
            frappe.log_error(title="backfill failed: {0}".format(name),
                             message=frappe.get_traceback())
    frappe.db.commit()
    return {"ok": len(ok), "failed": failed}
