# install_so_fetch.ps1 -- selecting a sales order fills customer + lays out stages
# Uses a Python AST merge for hooks.py so existing handlers cannot be lost.
# Run from inside C:\Users\simph\Downloads\sbi_projects_live

$ErrorActionPreference = "Stop"
$app = "sbi_projects"
$module = Join-Path $app "sbi_projects"
$projJs = Join-Path $app "public\js\project.js"
$hooksPy = Join-Path $app "hooks.py"
if (-not (Test-Path $module)) { Write-Error "Not in sbi_projects_live?"; exit 1 }
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

$c_py = @'
"""Pull details onto a Project when its Sales Order is set.

Selecting a sales order on the project form should fill in the customer and the
contract value immediately, and lay out the stage tasks from the order's
payment schedule -- without the user having to press a separate button.

Wired on Project validate, so it runs whether the sales order is set at
creation, added later, or changed.
"""

import frappe
from frappe.utils import flt


def sync_from_sales_order(doc, method=None):
	so_name = doc.get("sales_order")
	if not so_name:
		return

	so = frappe.db.get_value(
		"Sales Order", so_name,
		["customer", "customer_name", "rounded_total", "grand_total"],
		as_dict=True,
	)
	if not so:
		return

	# customer, only if the form has such a field and it is not already set
	if not doc.get("customer") and doc.meta.has_field("customer"):
		doc.customer = so.customer

	# contract value, if we track it and it is still blank
	if doc.meta.has_field("sbi_contract_value") and not doc.get("sbi_contract_value"):
		doc.sbi_contract_value = flt(so.rounded_total or so.grand_total)


def build_stages_if_new(doc, method=None):
	"""On first save with a sales order and no tasks yet, lay out the stages.

	Kept separate from sync_from_sales_order so the light-touch fetch always
	runs, while stage creation only happens when it is safe (no tasks yet).
	"""
	if not doc.get("sales_order"):
		return
	if frappe.db.exists("Task", {"project": doc.name}):
		return

	try:
		from sbi_projects.sbi_projects.project_hooks import create_stages_from_sales_order
		create_stages_from_sales_order(doc.name)
	except Exception:
		frappe.log_error(
			title="Auto stage creation failed: {0}".format(doc.name),
			message=frappe.get_traceback(),
		)
'@

$c_js = @'

// ---------------------------------------------------------------------------
// When a sales order is chosen on the Project form, fill the customer straight
// away so the user sees it before saving.
// ---------------------------------------------------------------------------

frappe.ui.form.on("Project", {
	sales_order(frm) {
		if (!frm.doc.sales_order) return;
		frappe.db.get_value(
			"Sales Order",
			frm.doc.sales_order,
			["customer", "rounded_total", "grand_total"]
		).then((r) => {
			const v = r.message || {};
			if (v.customer && frm.fields_dict.customer) {
				frm.set_value("customer", v.customer);
			}
			if (frm.fields_dict.sbi_contract_value && !frm.doc.sbi_contract_value) {
				frm.set_value("sbi_contract_value", v.rounded_total || v.grand_total || 0);
			}
		});
	},
});
'@

$c_merge = @'
"""Safely add the so_fetch handlers to Project's doc_events in hooks.py.

Rather than editing hooks.py with regexes (which broke doc_events once before),
this loads the file's doc_events dict, adds our two handlers, and rewrites only
that assignment.  Everything else in hooks.py is left byte-for-byte untouched.
"""

import ast
import io
import sys
import tokenize

HOOKS = sys.argv[1]
VALIDATE = "sbi_projects.sbi_projects.so_fetch.sync_from_sales_order"
BUILD = "sbi_projects.sbi_projects.so_fetch.build_stages_if_new"

src = open(HOOKS, encoding="utf-8").read()
tree = ast.parse(src)

# find the doc_events assignment node and its source span
node = None
for n in tree.body:
	if isinstance(n, ast.Assign):
		for t in n.targets:
			if isinstance(t, ast.Name) and t.id == "doc_events":
				node = n
if node is None:
	print("NO_DOC_EVENTS")
	sys.exit(2)

doc_events = ast.literal_eval(node.value)

proj = doc_events.setdefault("Project", {})

# --- validate: keep any existing handlers, add ours ---
def as_list(v):
	if v is None:
		return []
	return list(v) if isinstance(v, (list, tuple)) else [v]

val = as_list(proj.get("validate"))
if VALIDATE not in val:
	val.insert(0, VALIDATE)
proj["validate"] = val if len(val) > 1 else val[0]

# --- after_insert: append build, keep existing ---
ai = as_list(proj.get("after_insert"))
if BUILD not in ai:
	ai.append(BUILD)
proj["after_insert"] = ai if len(ai) > 1 else (ai[0] if ai else None)
if proj["after_insert"] is None:
	del proj["after_insert"]

# pretty-print the new dict
import pprint
new_literal = "doc_events = " + pprint.pformat(doc_events, indent=4, width=100, sort_dicts=False)

# replace the old assignment span with the new literal
lines = src.splitlines(keepends=True)
start = node.lineno - 1
end = node.end_lineno
new_src = "".join(lines[:start]) + new_literal + "\n" + "".join(lines[end:])

# sanity: it must still parse and still contain the old handlers
ast.parse(new_src)
for must in ["build_project_stages", "create_site_masters"]:
	if must in src and must not in new_src:
		print("LOST_HANDLER:" + must)
		sys.exit(3)

open(HOOKS, "w", encoding="utf-8").write(new_src)
print("OK")
'@

# 1. python module
[System.IO.File]::WriteAllText((Join-Path (Resolve-Path $module) "so_fetch.py"), $c_py, $utf8NoBom)
Write-Host "  wrote so_fetch.py" -ForegroundColor Green

# 2. append JS once
$js = [System.IO.File]::ReadAllText((Resolve-Path $projJs))
if ($js -match "sales_order\(frm\)") { Write-Host "  project.js already wired - skipped" -ForegroundColor Yellow }
else { [System.IO.File]::WriteAllText((Resolve-Path $projJs), $js.TrimEnd() + "`n" + $c_js + "`n", $utf8NoBom); Write-Host "  appended to project.js" -ForegroundColor Green }

# 3. merge hooks.py via python (safe)
$h = [System.IO.File]::ReadAllText((Resolve-Path $hooksPy))
if ($h -match "so_fetch") {
    Write-Host "  hooks.py already wired - skipped" -ForegroundColor Yellow
} else {
    $tmp = Join-Path $env:TEMP "sbi_merge_hooks.py"
    [System.IO.File]::WriteAllText($tmp, $c_merge, $utf8NoBom)
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
    if (-not $py) { Write-Error "Python not found on PATH - needed to merge hooks.py safely."; exit 1 }
    $out = & $py.Source $tmp (Resolve-Path $hooksPy).Path
    Write-Host ("  merge result: " + $out)
    if ($out -notmatch "OK") { Write-Error "hooks.py merge failed ($out) - not committing."; exit 1 }
    Write-Host "  wired hooks.py" -ForegroundColor Green
}

Write-Host ""; Write-Host "-- doc_events --" -ForegroundColor Cyan
Select-String -Path $hooksPy -Pattern "build_project_stages|create_site_masters|sync_from_sales_order|build_stages_if_new" | ForEach-Object { "  " + $_.Line.Trim() }

Write-Host ""; git status --short; Write-Host ""
Write-Host "CHECK: all four handler names must appear above." -ForegroundColor Yellow
$ans = Read-Host "Commit and push? (y/n)"
if ($ans -ne "y") { Write-Host ("Stopped. git checkout " + $hooksPy); exit 0 }
git add -A -- $app
git commit -m "feat: auto-fetch customer and stages when sales order set on project"
git push origin main
Write-Host "Pushed." -ForegroundColor Green
