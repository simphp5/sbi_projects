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
	rows = frappe.get_all(
		"Daily Work Log",
		filters={"project": project},
		fields=["task", "count(name) as n"],
		group_by="task",
	)
	return {r.task: r.n for r in rows if r.task}