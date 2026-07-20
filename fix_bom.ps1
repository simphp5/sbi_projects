# fix_bom.ps1 -- strip UTF-8 BOM from app files (PowerShell 5.1 adds one,
# which makes Python's json.load fail with "bad json" during bench migrate).
# Run from inside C:\Users\simph\Downloads\sbi_projects_live

$ErrorActionPreference = "Stop"
$root = "sbi_projects"
if (-not (Test-Path $root)) { Write-Error "Not found: $root -- are you in sbi_projects_live?"; exit 1 }

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$fixed = @()
$checked = 0

Get-ChildItem -Path $root -Recurse -Include *.json,*.py,*.js,*.txt -File | ForEach-Object {
    $checked++
    $bytes = [System.IO.File]::ReadAllBytes($_.FullName)
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        $text = [System.IO.File]::ReadAllText($_.FullName)   # decoder drops the BOM
        [System.IO.File]::WriteAllText($_.FullName, $text, $utf8NoBom)
        $fixed += $_.FullName
    }
}

Write-Host ("Checked {0} files." -f $checked) -ForegroundColor Cyan
if ($fixed.Count -eq 0) {
    Write-Host "No BOM found - nothing to fix." -ForegroundColor Yellow
} else {
    Write-Host ("Stripped BOM from {0} file(s):" -f $fixed.Count) -ForegroundColor Green
    $fixed | ForEach-Object { Write-Host ("  " + $_) }
}

# --- verify every doctype json actually parses ---
Write-Host ""
Write-Host "-- validating doctype JSON --" -ForegroundColor Cyan
$bad = @()
Get-ChildItem -Path (Join-Path $root "sbi_projects\doctype") -Recurse -Filter *.json -File | ForEach-Object {
    try {
        $j = Get-Content $_.FullName -Raw | ConvertFrom-Json
        Write-Host ("  ok  " + $j.name)
    } catch {
        $bad += $_.FullName
        Write-Host ("  BAD " + $_.FullName) -ForegroundColor Red
    }
}
if ($bad.Count -gt 0) { Write-Error "Some JSON still invalid - not pushing."; exit 1 }

Write-Host ""
git status --short
Write-Host ""
$ans = Read-Host "Commit and push? (y/n)"
if ($ans -ne "y") { Write-Host "Stopped. Nothing pushed." -ForegroundColor Yellow; exit 0 }
git add -A
git commit -m "fix: strip UTF-8 BOM that broke doctype json parsing during migrate"
git push origin main
Write-Host "Pushed. Now: Frappe Cloud -> Fetch Latest Updates -> Deploy" -ForegroundColor Green
