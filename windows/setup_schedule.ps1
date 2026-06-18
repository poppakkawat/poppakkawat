<#
.SYNOPSIS
    Register a Windows Scheduled Task that runs the polytrack daily report
    and saves it into your OneDrive "Prediction Market update" folder.

.USAGE
    Right-click > "Run with PowerShell", or from a PowerShell prompt:
        powershell -ExecutionPolicy Bypass -File .\windows\setup_schedule.ps1
    Optional custom time (24h):
        ... setup_schedule.ps1 -Time "07:30"

    Remove it later:
        Unregister-ScheduledTask -TaskName "Polytrack Daily Report" -Confirm:$false
#>

param(
    [string]$Time = "08:00",
    [string]$TaskName = "Polytrack Daily Report"
)

# Resolve paths relative to this script.
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$batPath   = Join-Path $scriptDir "run_report.bat"
$outDir    = Join-Path $env:USERPROFILE "OneDrive\Prediction Market update"

if (-not (Test-Path $batPath)) {
    Write-Error "Cannot find run_report.bat at $batPath"
    exit 1
}

# Make sure the output folder exists so OneDrive has somewhere to sync.
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$batPath`""
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

# Run as the current user, only when logged on (no password needed).
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Generates the daily Prediction Markets report into OneDrive." `
    -Force | Out-Null

Write-Host ""
Write-Host "Scheduled '$TaskName' to run daily at $Time." -ForegroundColor Green
Write-Host "Reports will appear in:" -ForegroundColor Green
Write-Host "  $outDir"
Write-Host ""
Write-Host "Run it now to test:  Start-ScheduledTask -TaskName `"$TaskName`""
