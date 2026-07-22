# fix_stage_tree_count.ps1 -- log-count query uses the query builder
# instead of a raw SQL string, which newer Frappe rejects.
# Run from inside C:\Users\simph\Downloads\sbi_projects_live

$ErrorActionPreference = "Stop"
$target = "sbi_projects\sbi_projects\stage_tree.py"
if (-not (Test-Path $target)) { Write-Error "Not found: $target"; exit 1 }
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

$code = @'
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
'@

[System.IO.File]::WriteAllText((Resolve-Path $target), $code, $utf8NoBom)
$b = [System.IO.File]::ReadAllBytes((Resolve-Path $target))
if ($b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF) { Write-Error "BOM"; exit 1 }
Write-Host "  wrote stage_tree.py (no BOM)" -ForegroundColor Green

Write-Host ""; git status --short; Write-Host ""
$ans = Read-Host "Commit and push? (y/n)"
if ($ans -ne "y") { Write-Host "Stopped." -ForegroundColor Yellow; exit 0 }
git add $target
git commit -m "fix: count work logs via query builder, not raw sql string"
git push origin main
Write-Host "Pushed. Deploy when ready (let it finish, do not push during build)." -ForegroundColor Green
