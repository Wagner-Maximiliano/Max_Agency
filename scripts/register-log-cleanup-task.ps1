<#
.SYNOPSIS
  Register the daily Max Agency log-retention cleanup as a hidden Windows Scheduled Task (FEAT-2).

.DESCRIPTION
  Registers 'MaxAgencyLogCleanup' to run scripts\clean-logs.ps1 once a day, deleting log files
  older than -RetentionDays (default 7) so the gate's transcripts + decision logs do not grow
  without bound. Idempotent: re-running updates the task in place (does not duplicate it). Runs
  windowless / hidden, the same style as the gate task. ASCII-only on purpose (PowerShell reads
  .ps1 as cp1252 without a BOM, so non-ASCII chars break parsing).

.EXAMPLE
  pwsh scripts/register-log-cleanup-task.ps1
.EXAMPLE
  pwsh scripts/register-log-cleanup-task.ps1 -RetentionDays 30 -At 02:30
.NOTES
  Remove with:  Unregister-ScheduledTask -TaskName MaxAgencyLogCleanup -Confirm:$false
  Inspect with: Get-ScheduledTask -TaskName MaxAgencyLogCleanup ; Get-ScheduledTaskInfo MaxAgencyLogCleanup
#>
param(
  [int]$RetentionDays = 7,
  [string]$At = "03:30",                          # daily run time (local)
  [string]$TaskName = "MaxAgencyLogCleanup",
  [string]$RepoRoot
)

$ErrorActionPreference = "Stop"
if (-not $RepoRoot) {
  $scriptDir = if ($PSScriptRoot) { $PSScriptRoot }
               elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath }
               else { (Get-Location).Path }
  $RepoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
}

$cleaner = Join-Path $RepoRoot "scripts\clean-logs.ps1"
if (-not (Test-Path $cleaner)) { throw "clean-logs.ps1 not found at $cleaner" }

# Prefer pwsh (PowerShell 7) if present, else Windows PowerShell; run hidden + no profile.
$psExe = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
if (-not $psExe) { $psExe = (Get-Command powershell -ErrorAction SilentlyContinue).Source }
if (-not $psExe) { throw "neither pwsh nor powershell found on PATH" }

$argList = @("-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
             "-ExecutionPolicy", "Bypass", "-File", "`"$cleaner`"",
             "-RetentionDays", $RetentionDays, "-RepoRoot", "`"$RepoRoot`"")

$action  = New-ScheduledTaskAction -Execute $psExe -Argument ($argList -join " ") -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -Hidden `
             -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
  -Settings $settings -Principal $principal -Force | Out-Null

Write-Host "Registered scheduled task '$TaskName': daily at $At, deletes logs older than $RetentionDays day(s)."
Write-Host "Disable: Disable-ScheduledTask -TaskName $TaskName | Remove: Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
