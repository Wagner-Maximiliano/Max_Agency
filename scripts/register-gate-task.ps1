<#
.SYNOPSIS
  Register the Max Agency gate as a Windows Scheduled Task -- the single scheduled job that
  replaces the retired WSL hermes tick timers (Phase 2F).

.DESCRIPTION
  The gate is safe to schedule: with an empty board (no open issues carrying the scope label)
  it exits at zero cost. The scope label (`AI` in production) is the human opt-in + kill
  switch -- nothing is dispatched until a human adds it to an issue. A single run lock + the
  task's IgnoreNew policy prevent overlapping runs.

  For a conservative first deployment use `-Mode deterministic-only` (no LLM dispatch / no
  merge) or `-NoAutoMerge` (the CTO can approve but every merge waits for a human).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/register-gate-task.ps1 -Repo owner/repo
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/register-gate-task.ps1 -Repo owner/repo -Mode deterministic-only -IntervalMinutes 10
.NOTES
  One task PER repo. The task name defaults to "MaxAgencyGate-<owner>-<repo>" (slugged) so
  Max Agency can run several projects at once, each with its own tick + its own run lock.
  List all:     Get-ScheduledTask -TaskName "MaxAgencyGate-*"
  Remove one:   Unregister-ScheduledTask -TaskName "MaxAgencyGate-<slug>" -Confirm:$false
#>
param(
  [Parameter(Mandatory = $true)][string]$Repo,
  [int]$IntervalMinutes = 5,
  [ValidateSet("dry-run", "deterministic-only", "dispatch-enabled")][string]$Mode = "dispatch-enabled",
  [string]$ScopeLabel = "AI",
  [switch]$NoAutoMerge,
  [string]$CoderModel,                         # per-repo coder model (else the gate default from gate/models.env)
  [string]$TaskName,                         # default: per-repo unique name (one task per project)
  [string]$PythonExe,
  [int]$StaleMin = 35,                       # > the coder timeout (min) so the lock isn't reclaimed mid-build
  [string]$RepoRoot
)

$ErrorActionPreference = "Stop"

# One scheduled task per project: derive a unique, stable task name from the repo so Max Agency
# can service several repos at once (each its own tick). Override with -TaskName if needed.
if (-not $TaskName) {
  $slug = ($Repo -replace '[^A-Za-z0-9._-]', '-')
  $TaskName = "MaxAgencyGate-$slug"
}

if (-not $RepoRoot) {
  # $PSScriptRoot can be empty depending on how the script is launched; fall back to the
  # script's own path, then to the current directory.
  $scriptDir = if ($PSScriptRoot) { $PSScriptRoot }
               elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath }
               else { (Get-Location).Path }
  $RepoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
}

if (-not $PythonExe) {
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if (-not $cmd) { throw "python not found on PATH; pass -PythonExe <path>" }
  $PythonExe = $cmd.Source
}
# Prefer pythonw.exe (the windowless interpreter) so the scheduled task runs with NO console
# window. Combined with CREATE_NO_WINDOW on the gate's child processes (gh/codex/wsl/claude),
# the gate runs fully silent in the background.
$pythonw = Join-Path (Split-Path -Parent $PythonExe) "pythonw.exe"
if (Test-Path $pythonw) { $PythonExe = $pythonw }

$gate = Join-Path $RepoRoot "gate\gate.py"
if (-not (Test-Path $gate)) { throw "gate.py not found at $gate" }

$argList = @("`"$gate`"", "--repo", $Repo, "--mode", $Mode, "--scope-label", $ScopeLabel,
             "--stale-min", $StaleMin)
if ($NoAutoMerge) { $argList += "--no-auto-merge" }
if ($CoderModel)  { $argList += @("--coder-model", "`"$CoderModel`"") }

$action  = New-ScheduledTaskAction -Execute $PythonExe -Argument ($argList -join " ") -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
             -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -Hidden `
             -ExecutionTimeLimit (New-TimeSpan -Hours 1) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
  -Settings $settings -Principal $principal -Force | Out-Null

$mergeNote = if ($Mode -eq "dispatch-enabled" -and -not $NoAutoMerge) { " (auto-merge ON)" } else { "" }
Write-Host "Registered scheduled task '$TaskName': $Mode every $IntervalMinutes min on $Repo (scope '$ScopeLabel')$mergeNote."
Write-Host "Disable: Disable-ScheduledTask -TaskName $TaskName | Remove: Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
