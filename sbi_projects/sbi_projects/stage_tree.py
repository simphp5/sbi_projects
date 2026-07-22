"""Stage tree shown on the Project form.

The task list already lives in ERPNext, but a site manager opening a project
wants one thing: which stage is where, what it was budgeted, what it has cost,
and a way to file today's work against it.  This assembles exactly that.
"""

import frappe
from frappe.utils import flt


@frappe.whitelist()
def get_stage_tree(project):
	"""Tasks for a project as a flat list with parent links, plus totals."""
	if not project:
		return {"stages": [], "totals": {}}

	meta = frappe.get_meta("Task")
	optional = [f for f in ("sbi_stage", "sbi_stage_budget", "sbi_total_budget",
	                        "sbi_total_actual", "sbi_invoice_portion")
	            if meta.has_field(f)]

	fields = (["name", "subject", "status", "is_group", "parent_task",
	           "task_weight", "progress", "exp_end_date"] + optional)

	tasks = frappe.get_all(
		"Task",
		filters={"project": project},
		fields=fields,
		order_by="lft asc" if meta.has_field("lft") else "creation asc",
	)
	if not tasks:
		return {"stages": [], "totals": {}}

	counts = log_counts(project)

	for t in tasks:
		t["log_count"] = counts.get(t.name, 0)
		t["budget"] = flt(t.get("sbi_total_budget")) or flt(t.get("sbi_stage_budget"))
		t["actual"] = flt(t.get("sbi_total_actual"))
		t["variance"] = t["budget"] - t["actual"]

	totals = {
		"budget": sum(t["budget"] for t in tasks if not t.get("parent_task")),
		"actual": sum(t["actual"] for t in tasks if not t.get("parent_task")),
		"count": len(tasks),
		"logs": sum(t["log_count"] for t in tasks),
	}
	totals["variance"] = totals["budget"] - totals["actual"]

	return {"stages": tasks, "totals": totals}


def log_counts(project):
	"""How many daily work logs exist per task."""
	if not frappe.db.exists("DocType", "Daily Work Log"):
		return {}
	# Count logs per task without a raw SQL string in the field list, which
	# newer Frappe rejects.  A grouped count via the query builder is portable.
	from frappe.query_builder.functions import Count

	dwl = frappe.qb.DocType("Daily Work Log")
	rows = (
		frappe.qb.from_(dwl)
		.select(dwl.task, Count(dwl.name).as_("n"))
		.where(dwl.project == project)
		.where(dwl.task.isnotnull())
		.groupby(dwl.task)
	).run(as_dict=True)
	return {r["task"]: r["n"] for r in rows if r.get("task")}


# ---------------------------------------------------------------------------
# Owner budget panel -- read and save the planned amount per account.
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_project_budget(project):
	"""Budget rows for a project, plus the contract net for reference."""
	if not project:
		return {"rows": [], "net": 0}

	so = frappe.db.get_value("Project", project, "sales_order")
	net = flt(frappe.db.get_value("Sales Order", so, "net_total")) if so else 0

	rows = frappe.get_all(
		"Budget",
		filters={"project": project},
		fields=["name", "account", "budget_amount"],
		order_by="account",
	)
	for r in rows:
		r["account_name"] = frappe.db.get_value("Account", r["account"], "account_name") or r["account"]

	return {"rows": rows, "net": net}


@frappe.whitelist()
def save_project_budget(project, updates):
	"""Update budget amounts per account for a project.

	updates is a JSON list of {account, amount}.  A row with an amount is
	created if it does not exist yet, so the owner can allocate to any account.
	"""
	import json

	if isinstance(updates, str):
		updates = json.loads(updates)

	company = frappe.db.get_value("Project", project, "company") \
		or frappe.defaults.get_user_default("company")
	fy = frappe.db.get_value("Fiscal Year", {"disabled": 0}, "name")

	saved = 0
	for u in updates:
		account = u.get("account")
		amount = flt(u.get("amount"))
		if not account:
			continue

		existing = frappe.db.get_value(
			"Budget",
			{"project": project, "account": account, "from_fiscal_year": fy},
			"name",
		)
		if existing:
			frappe.db.set_value("Budget", existing, "budget_amount", amount)
		elif amount:
			doc = frappe.get_doc({
				"doctype": "Budget",
				"budget_against": "Project",
				"project": project,
				"company": company,
				"account": account,
				"from_fiscal_year": fy,
				"to_fiscal_year": fy,
				"distribution_frequency": "Monthly",
				"budget_amount": amount,
				"action_if_annual_budget_exceeded": "Warn",
				"action_if_accumulated_monthly_budget_exceeded": "Warn",
			})
			doc.insert(ignore_permissions=True)
		saved += 1

	frappe.db.commit()
	return {"saved": saved}