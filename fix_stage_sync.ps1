# fix_stage_sync.ps1 -- add payment-schedule stage sync + wire hooks
# Run from inside C:\Users\simph\Downloads\sbi_projects_live

$ErrorActionPreference = "Stop"
$hooksFn = "sbi_projects\sbi_projects\project_hooks.py"
$hooksPy = "sbi_projects\hooks.py"

if (-not (Test-Path $hooksFn)) { Write-Error "Not found: $hooksFn -- are you in sbi_projects_live?"; exit 1 }
if (-not (Test-Path $hooksPy)) { Write-Error "Not found: $hooksPy"; exit 1 }

# ---- 1. append the function ----
if (Select-String -Path $hooksFn -Pattern "def sync_payment_schedule_stage" -Quiet) {
    Write-Host "Function already present - skipped." -ForegroundColor Yellow
} else {
$code = @'


# ---------------------------------------------------------------------------
# Payment schedule -> stage sync
#
# ERPNext builds payment_schedule rows server-side from the Payment Terms
# Template via get_payment_terms(), which only returns standard fields.  The
# fetch_from on sbi_stage is a client-side mechanism and does not fire for
# those generated rows, so we resolve it here on validate.
# ---------------------------------------------------------------------------

def sync_payment_schedule_stage(doc, method=None):
    """Fill sbi_stage on each payment_schedule row from its Payment Term."""
    rows = doc.get("payment_schedule") or []
    if not rows:
        return

    cache = {}
    for row in rows:
        if not row.get("payment_term") or row.get("sbi_stage"):
            continue
        term = row.payment_term
        if term not in cache:
            cache[term] = frappe.db.get_value("Payment Term", term, "sbi_stage")
        if cache[term]:
            row.sbi_stage = cache[term]
'@
    Add-Content -Path $hooksFn -Value $code -Encoding UTF8
    Write-Host "Appended sync_payment_schedule_stage to $hooksFn" -ForegroundColor Green
}

# ---- 2. wire doc_events ----
$h = Get-Content $hooksPy -Raw
if ($h -match "sync_payment_schedule_stage") {
    Write-Host "hooks.py already wired - skipped." -ForegroundColor Yellow
} else {
    $entry = @'
doc_events = {
    "Quotation": {
        "validate": "sbi_projects.sbi_projects.project_hooks.sync_payment_schedule_stage",
    },
    "Sales Order": {
        "validate": "sbi_projects.sbi_projects.project_hooks.sync_payment_schedule_stage",
    },
    "Sales Invoice": {
        "validate": "sbi_projects.sbi_projects.project_hooks.sync_payment_schedule_stage",
    },
'@
    if ($h -notmatch "doc_events\s*=\s*\{") { Write-Error "Could not find doc_events in hooks.py"; exit 1 }
    $h = $h -replace "doc_events\s*=\s*\{", $entry
    Set-Content -Path $hooksPy -Value $h -NoNewline -Encoding UTF8
    Write-Host "Wired doc_events in $hooksPy" -ForegroundColor Green
}

Write-Host ""
Write-Host "-- doc_events now --" -ForegroundColor Cyan
Select-String -Path $hooksPy -Pattern "doc_events" -Context 0,16 | ForEach-Object { $_.Line; $_.Context.PostContext }

Write-Host ""
git diff --stat

$ans = Read-Host "Commit and push? (y/n)"
if ($ans -ne "y") { Write-Host "Stopped. Nothing pushed." -ForegroundColor Yellow; exit 0 }
git add $hooksFn $hooksPy
git commit -m "fix: sync sbi_stage onto payment schedule rows server-side"
git push origin main
Write-Host "Pushed. Now: Frappe Cloud -> Fetch Latest Updates -> Deploy" -ForegroundColor Green
