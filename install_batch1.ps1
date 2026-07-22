# install_batch1.ps1 -- payment terms on net total, net/GST/grand display,
#   DWL budget helper, and the stage-tree work-log-count fix.
# hooks.py is merged with Python (AST) so existing handlers cannot be lost.
# Run from inside C:\Users\simph\Downloads\sbi_projects_live

$ErrorActionPreference = "Stop"
$app = "sbi_projects"
$module = Join-Path $app "sbi_projects"
$projJs = Join-Path $app "public\js\project.js"
$hooksPy = Join-Path $app "hooks.py"
if (-not (Test-Path $module)) { Write-Error "Not in sbi_projects_live?"; exit 1 }
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $py) { Write-Error "Python needed on PATH to merge hooks.py safely."; exit 1 }

$c_payment_terms_net_py = @'
"""Recompute payment-schedule amounts on the net total, not the grand total.

By default ERPNext splits the grand total (net + GST) across payment terms.
SBI's contracts quote the payment plan on the net value, with GST shown and
billed separately, so this recomputes each row from net_total after the
standard calculation has run.

Wired on validate for Quotation, Sales Order and Sales Invoice.  Idempotent:
re-running produces the same numbers.
"""

import frappe
from frappe.utils import flt


def set_payment_terms_on_net(doc, method=None):
	schedule = doc.get("payment_schedule") or []
	if not schedule:
		return

	net = flt(doc.get("net_total"))
	if not net:
		return

	# distribute net by each row's invoice_portion; if portions are blank,
	# fall back to the ratio of the existing amount to the grand total.
	grand = flt(doc.get("grand_total")) or flt(doc.get("rounded_total"))

	running = 0.0
	last = len(schedule) - 1
	for i, row in enumerate(schedule):
		portion = flt(row.get("invoice_portion"))
		if portion:
			amount = net * portion / 100.0
		elif grand:
			amount = net * (flt(row.get("payment_amount")) / grand)
		else:
			amount = flt(row.get("payment_amount"))

		amount = flt(amount, 2)

		# put any rounding remainder on the final row so the total is exact
		if i == last:
			amount = flt(net - running, 2)
		running += amount

		row.payment_amount = amount
		if hasattr(row, "base_payment_amount"):
			row.base_payment_amount = amount
		# keep outstanding in step for a fresh (unpaid) document
		if not flt(row.get("paid_amount")):
			row.outstanding = amount
'@

$c_dwl_budget_py = @'
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
'@

$c_stage_tree_py = @'
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

$c_totals_js = @'

// ---------------------------------------------------------------------------
// Show net / GST / grand total as a clear summary on Quotation and Sales Order,
// so it is obvious the payment plan is on the net figure.
// ---------------------------------------------------------------------------

["Quotation", "Sales Order"].forEach(function (dt) {
	frappe.ui.form.on(dt, {
		refresh(frm) {
			sbi_render_totals(frm);
		},
		net_total(frm) { sbi_render_totals(frm); },
		grand_total(frm) { sbi_render_totals(frm); },
	});
});

function sbi_render_totals(frm) {
	const f = frm.get_field("sbi_totals_html");
	if (!f || !f.$wrapper) return;

	const net = flt(frm.doc.net_total);
	const tax = flt(frm.doc.total_taxes_and_charges);
	const grand = flt(frm.doc.grand_total) || flt(frm.doc.rounded_total);
	if (!net && !grand) { f.$wrapper.html(""); return; }

	f.$wrapper.html(`
		<div style="border:1px solid var(--border-color);border-radius:4px;overflow:hidden;max-width:360px">
			<div style="display:flex;justify-content:space-between;padding:8px 12px;border-bottom:1px solid var(--border-color)">
				<span class="text-muted">Net total (payment plan basis)</span>
				<b style="font-variant-numeric:tabular-nums">${format_currency(net)}</b>
			</div>
			<div style="display:flex;justify-content:space-between;padding:8px 12px;border-bottom:1px solid var(--border-color)">
				<span class="text-muted">GST</span>
				<span style="font-variant-numeric:tabular-nums">${format_currency(tax)}</span>
			</div>
			<div style="display:flex;justify-content:space-between;padding:8px 12px;background:var(--fg-color)">
				<span>Grand total</span>
				<b style="font-variant-numeric:tabular-nums">${format_currency(grand)}</b>
			</div>
		</div>`);
}
'@

$c_merge = @'
"""Add set_payment_terms_on_net to Quotation/Sales Order/Sales Invoice validate,
AFTER the existing sync_payment_schedule_stage handler.

Loads doc_events, appends our handler to each target's validate list (converting
a single string to a list as needed), preserves everything else, and rewrites
only the doc_events assignment.
"""

import ast
import sys
import pprint

HOOKS = sys.argv[1]
NET = "sbi_projects.sbi_projects.payment_terms_net.set_payment_terms_on_net"
TARGETS = ["Quotation", "Sales Order", "Sales Invoice"]

src = open(HOOKS, encoding="utf-8").read()
tree = ast.parse(src)

node = None
for n in tree.body:
	if isinstance(n, ast.Assign):
		for t in n.targets:
			if isinstance(t, ast.Name) and t.id == "doc_events":
				node = n
if node is None:
	print("NO_DOC_EVENTS"); sys.exit(2)

doc_events = ast.literal_eval(node.value)


def as_list(v):
	if v is None:
		return []
	return list(v) if isinstance(v, (list, tuple)) else [v]


for dt in TARGETS:
	block = doc_events.setdefault(dt, {})
	val = as_list(block.get("validate"))
	if NET not in val:
		val.append(NET)  # after any existing handler (stage sync runs first)
	block["validate"] = val if len(val) > 1 else val[0]

new_literal = "doc_events = " + pprint.pformat(doc_events, indent=4, width=100, sort_dicts=False)

lines = src.splitlines(keepends=True)
new_src = "".join(lines[:node.lineno - 1]) + new_literal + "\n" + "".join(lines[node.end_lineno:])

ast.parse(new_src)
# every previously-present handler must survive
for must in ["sync_payment_schedule_stage", "sync_from_sales_order",
             "build_stages_if_new", "build_project_stages", "create_site_masters"]:
	if must in src and must not in new_src:
		print("LOST:" + must); sys.exit(3)

open(HOOKS, "w", encoding="utf-8").write(new_src)
print("OK")
'@

$pyTargets = @(
    @{ path = "sbi_projects\sbi_projects\payment_terms_net.py"; body = $c_payment_terms_net_py },
    @{ path = "sbi_projects\sbi_projects\dwl_budget.py"; body = $c_dwl_budget_py },
    @{ path = "sbi_projects\sbi_projects\stage_tree.py"; body = $c_stage_tree_py }
)
foreach ($t in $pyTargets) {
    [System.IO.File]::WriteAllText((Join-Path (Get-Location) $t.path), $t.body, $utf8NoBom)
    Write-Host ("  wrote " + $t.path) -ForegroundColor Green
}

$js = [System.IO.File]::ReadAllText((Resolve-Path $projJs))
if ($js -match "sbi_render_totals") { Write-Host "  totals JS already present - skipped" -ForegroundColor Yellow }
else { [System.IO.File]::WriteAllText((Resolve-Path $projJs), $js.TrimEnd() + "`n" + $c_totals_js + "`n", $utf8NoBom); Write-Host "  appended totals display to project.js" -ForegroundColor Green }

$h = [System.IO.File]::ReadAllText((Resolve-Path $hooksPy))
if ($h -match "payment_terms_net") { Write-Host "  hooks.py already wired - skipped" -ForegroundColor Yellow }
else {
    $tmp = Join-Path $env:TEMP "sbi_merge_net.py"
    [System.IO.File]::WriteAllText($tmp, $c_merge, $utf8NoBom)
    $out = & $py.Source $tmp (Resolve-Path $hooksPy).Path
    Write-Host ("  merge: " + $out)
    if ($out -notmatch "OK") { Write-Error "hooks merge failed ($out)"; exit 1 }
    Write-Host "  wired hooks.py" -ForegroundColor Green
}

Write-Host ""; Write-Host "-- validate handlers --" -ForegroundColor Cyan
Select-String -Path $hooksPy -Pattern "sync_payment_schedule_stage|set_payment_terms_on_net|build_project_stages|create_site_masters|sync_from_sales_order" | ForEach-Object { "  " + $_.Line.Trim() }

Write-Host ""; git status --short; Write-Host ""
Write-Host "CHECK: all five handler names must appear above." -ForegroundColor Yellow
$ans = Read-Host "Commit and push? (y/n)"
if ($ans -ne "y") { Write-Host ("Stopped. git checkout " + $hooksPy); exit 0 }
git add -A -- $app
git commit -m "feat: payment terms on net total, net/GST/grand display, DWL budget helper, stage-tree count fix"
git push origin main
Write-Host "Pushed. Deploy ONCE (let it finish, no push during build)." -ForegroundColor Green
