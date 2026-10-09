# Starts the Tally <-> ERPNext agent automatically whenever this Windows user logs in.
# Put this file, tally_agent.py and config.json in one folder (e.g. C:\TallyAgent), then in PowerShell:
#   powershell -ExecutionPolicy Bypass -File .\agent_autostart.ps1
# To remove:  Unregister-ScheduledTask -TaskName "Tally ERPNext Agent" -Confirm:$false

$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $dir "tally_agent.py"
if (-not (Test-Path $script)) { throw "tally_agent.py not found in $dir" }
if (-not (Test-Path (Join-Path $dir "config.json"))) {
    throw "config.json not found. In ERPNext: Tally Settings > Agent > Generate Agent Key, and save it in $dir"
}

$py = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (-not $py) { throw "Python not found. Install Python 3 from python.org and tick 'Add python.exe to PATH'." }
$pyw = Join-Path (Split-Path $py) "pythonw.exe"
if (-not (Test-Path $pyw)) { $pyw = $py }

Write-Host "Testing connections..."
& $py $script test
if ($LASTEXITCODE -ne 0) { throw "Connection test failed - fix the problem above and run this again." }

$action   = New-ScheduledTaskAction -Execute $pyw -Argument "`"$script`"" -WorkingDirectory $dir
$trigger  = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
            -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "Tally ERPNext Agent" -Action $action -Trigger $trigger -Settings $settings `
    -Description "Syncs TallyPrime with ERPNext" -Force | Out-Null
Start-ScheduledTask -TaskName "Tally ERPNext Agent"
Write-Host "Agent installed and running. Log: $(Join-Path $dir 'tally_agent.log')" -ForegroundColor Green
