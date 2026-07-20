# fix_fieldname.ps1 -- correct Project fieldname (custom_* -> sbi_*) and push
# Run from inside C:\Users\simph\Downloads\sbi_projects_live

$ErrorActionPreference = "Stop"
$target = "sbi_projects\sbi_projects\project_hooks.py"

if (-not (Test-Path $target)) {
    Write-Error "Not found: $target  -- are you inside sbi_projects_live?"; exit 1
}

$content = Get-Content $target -Raw

if ($content -notmatch 'custom_site_warehouse') {
    Write-Host "Already fixed - no 'custom_site_warehouse' found. Nothing to do." -ForegroundColor Yellow
    exit 0
}

# drop the cost-center line (that field does not exist on Project)
$content = $content -replace '(?m)^\s*_set_if_field_exists\(doc, "custom_site_cost_center", cc\)\r?\n', ''
# correct the warehouse fieldname
$content = $content -replace '_set_if_field_exists\(doc, "custom_site_warehouse", wh\)', '_set_if_field_exists(doc, "sbi_site_warehouse", wh)'

Set-Content -Path $target -Value $content -NoNewline -Encoding UTF8
Write-Host "Edited $target" -ForegroundColor Green

Write-Host ""
Write-Host "-- _set_if_field_exists calls now --" -ForegroundColor Cyan
Select-String -Path $target -Pattern "_set_if_field_exists\(doc" | ForEach-Object { $_.Line.Trim() }

if (Select-String -Path $target -Pattern "custom_site" -Quiet) {
    Write-Error "Still found 'custom_site' references - aborting before push."; exit 1
}

Write-Host ""
Write-Host "-- git diff --stat --" -ForegroundColor Cyan
git diff --stat

Write-Host ""
$ans = Read-Host "Commit and push these changes? (y/n)"
if ($ans -ne "y") { Write-Host "Stopped. Nothing pushed." -ForegroundColor Yellow; exit 0 }

git add $target
git commit -m "fix: use sbi_site_warehouse fieldname on Project"
git push origin main

Write-Host ""
Write-Host "Pushed. Now: Frappe Cloud -> Fetch Latest Updates -> Deploy" -ForegroundColor Green
