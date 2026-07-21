"""Budget-vs-spent figures for a Daily Work Log, shown while it is being filled.

When a site engineer opens a work log against a task, they see how much budget
that task's stage has by category and how much is already spent, so overspend is
visible before approval rather than after.
"""

import frappe
from frappe.utils import flt


@frappe.whitelist()
def get_task_budget_status(task):
	"""Return per-category budget, spent and remaining for a task."""
	if not task or not frappe.db.exists("Task", task):
		return {"rows": [], "totals": {}}

	project = frappe.db.get_value("Task", task, "project")

	# budget rows recorded on the task (Task Budget Detail child table)
	budget = {}
	tdoc = frappe.get_doc("Task", task)
	for r in (tdoc.get("sbi_budget_details") or []):
		budget[r.site_cost_category] = flt(r.budget_amount)

	# spent so far: approved daily work logs on this task
	spent = _spent_by_category(task)

	categories = sorted(set(list(budget.keys()) + list(spent.keys())))
	rows = []
	tb = ts = 0.0
	for cat in categories:
		b = flt(budget.get(cat))
		s = flt(spent.get(cat))
		rows.append({"category": cat, "budget": b, "spent": s, "remaining": b - s})
		tb += b
		ts += s

	return {
		"task": task,
		"project": project,
		"rows": rows,
		"totals": {"budget": tb, "spent": ts, "remaining": tb - ts},
	}


def _spent_by_category(task):
	spent = {}

	# other-cost rows on approved logs
	rows = frappe.db.sql("""
		select c.site_cost_category as cat, sum(c.amount) as amt
		from `tabDaily Work Log Cost` c
		inner join `tabDaily Work Log` l on l.name = c.parent
		where l.task = %s and l.workflow_state = 'Approved'
		group by c.site_cost_category
	""", (task,), as_dict=True)
	for r in rows:
		if r.cat:
			spent[r.cat] = flt(spent.get(r.cat)) + flt(r.amt)

	# material -> the Material category
	mat_cat = frappe.db.get_value("Site Cost Category", {"category_name": "Material"}, "name")
	if mat_cat:
		tot = frappe.db.sql("""
			select sum(m.amount) from `tabDaily Work Log Material` m
			inner join `tabDaily Work Log` l on l.name = m.parent
			where l.task = %s and l.workflow_state = 'Approved'
		""", (task,))
		if tot and tot[0][0]:
			spent[mat_cat] = flt(spent.get(mat_cat)) + flt(tot[0][0])

	# labour -> whichever category is flagged as labour
	lab_cat = frappe.db.get_value("Site Cost Category", {"is_labour_cost": 1}, "name")
	if lab_cat:
		tot = frappe.db.sql("""
			select sum(sbi_total_labour_cost) from `tabDaily Work Log`
			where task = %s and workflow_state = 'Approved'
		""", (task,))
		if tot and tot[0][0]:
			spent[lab_cat] = flt(spent.get(lab_cat)) + flt(tot[0][0])

	return spent