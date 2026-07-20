# fix_duplicate_guard.ps1 -- stop double-clicking the stage buttons from
# creating a second set of tasks.
# Run from inside C:\Users\simph\Downloads\sbi_projects_live

$ErrorActionPreference = "Stop"
$target = "sbi_projects\sbi_projects\project_hooks.py"

if (-not (Test-Path $target)) { Write-Error "Not found: $target -- are you in sbi_projects_live?"; exit 1 }

$src = Get-Content $target -Raw

if ($src -match 'Stages already exist for this project') {
    Write-Host "Guard already present - nothing to do." -ForegroundColor Yellow; exit 0
}

$guard = @'
	if frappe.db.exists("Task", {"project": project}):
		frappe.msgprint(
			_("Stages already exist for this project. Delete the existing tasks first if you want to regenerate them."),
			indicator="orange",
			alert=True,
		)
		return 0
'@
$guard = $guard -replace "`r`n", "`n"

$patSO  = '(if not prj\.sales_order:\r?\n\s*frappe\.throw\(_\("This project is not linked to a Sales Order"\)\)\r?\n)'
$patTPL = '(if not prj\.sbi_project_template:\r?\n\s*frappe\.throw\(_\("No Project Template selected"\)\)\r?\n)'

foreach ($p in @($patSO, $patTPL)) {
    $m = [regex]::Matches($src, $p)
    if ($m.Count -ne 1) { Write-Error "Expected 1 anchor match, found $($m.Count). Aborting - file not modified."; exit 1 }
    $src = [regex]::Replace($src, $p, { param($x) $x.Groups[1].Value + $guard + "`n" }, 1)
}

Set-Content -Path $target -Value $src -NoNewline -Encoding UTF8
Write-Host "Added duplicate guards to both stage functions." -ForegroundColor Green

Write-Host ""
Write-Host "-- guards now in file --" -ForegroundColor Cyan
Select-String -Path $target -Pattern 'frappe.db.exists\("Task"' | ForEach-Object { "  line " + $_.LineNumber + ": " + $_.Line.Trim() }

Write-Host ""
git diff --stat

$ans = Read-Host "Commit and push? (y/n)"
if ($ans -ne "y") { Write-Host "Stopped. Run: git checkout $target  to undo." -ForegroundColor Yellow; exit 0 }
git add $target
git commit -m "fix: guard against duplicate stage creation on repeat button click"
git push origin main
Write-Host "Pushed. Now: Frappe Cloud -> Fetch Latest Updates -> Deploy" -ForegroundColor Green
