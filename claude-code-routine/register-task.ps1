[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Repo,
  [Parameter(Mandatory=$true)][string]$ProjectPath,
  [int]$IntervalMinutes = 5,
  [string]$TaskName = "MaxAgency-ClaudeCodeRoutine"
)

$ErrorActionPreference = "Stop"

$promptPath = Join-Path $PSScriptRoot "poll-and-pickup.md"
if (-not (Test-Path $promptPath)) { throw "poll-and-pickup.md not found at $promptPath" }

$runTickPath = Join-Path $PSScriptRoot "run-tick.ps1"
if (-not (Test-Path $runTickPath)) { throw "run-tick.ps1 not found at $runTickPath" }

$vbsPath = Join-Path $PSScriptRoot "run-tick.vbs"
if (-not (Test-Path $vbsPath)) { throw "run-tick.vbs not found at $vbsPath" }

$claudeCmd = (Get-Command claude -ErrorAction SilentlyContinue)
if (-not $claudeCmd) { throw "Claude Code CLI 'claude' not found on PATH. Install from https://claude.ai/download" }

# Launch via wscript.exe + run-tick.vbs so the task runs with NO visible console window.
# wscript.exe is a GUI host — it never creates a console window, and window-style 0
# in the VBScript ensures the spawned PowerShell is also invisible.
$action = New-ScheduledTaskAction `
  -Execute "wscript.exe" `
  -Argument "/nologo `"$vbsPath`" `"$runTickPath`" `"-Repo $Repo -AgencyPath $ProjectPath`""

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
  -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
  -RepetitionDuration (New-TimeSpan -Days 3650)

$settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -StartWhenAvailable `
  -ExecutionTimeLimit (New-TimeSpan -Minutes 25) `
  -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $action `
  -Trigger $trigger `
  -Settings $settings `
  -Principal $principal `
  -Description "Max Agency Claude Code routine - polls GitHub every $IntervalMinutes min, picks up assigned issues, exits." `
  -Force | Out-Null

Write-Information "Registered scheduled task '$TaskName' - runs every $IntervalMinutes min against $Repo" -InformationAction Continue
Write-Information "To inspect: Get-ScheduledTask -TaskName '$TaskName'" -InformationAction Continue
Write-Information "To unregister: Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false" -InformationAction Continue
