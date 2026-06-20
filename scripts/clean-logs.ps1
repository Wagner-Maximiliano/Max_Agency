<#
.SYNOPSIS
  Delete Max Agency log files older than a retention window (FEAT-2).

.DESCRIPTION
  Removes any file under the gate's log trees (runtime\logs and logs) whose LastWriteTime is
  older than -RetentionDays. This bounds the growth of the per-run decision JSONL and the
  (much larger) LLM transcripts. Safe to run by hand; the MaxAgencyLogCleanup scheduled task
  runs it daily. ASCII-only on purpose (PowerShell reads .ps1 as cp1252 without a BOM).

.EXAMPLE
  pwsh scripts/clean-logs.ps1                       # delete logs older than 7 days
.EXAMPLE
  pwsh scripts/clean-logs.ps1 -RetentionDays 30     # keep a month
#>
param(
  [int]$RetentionDays = 7,
  [string]$RepoRoot
)

$ErrorActionPreference = "Stop"
if (-not $RepoRoot) {
  $scriptDir = if ($PSScriptRoot) { $PSScriptRoot }
               elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath }
               else { (Get-Location).Path }
  $RepoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
}

$cutoff = (Get-Date).AddDays(-[math]::Abs($RetentionDays))
$roots = @((Join-Path $RepoRoot "runtime\logs"), (Join-Path $RepoRoot "logs"))
$removed = 0
foreach ($root in $roots) {
  if (-not (Test-Path $root)) { continue }
  Get-ChildItem -Path $root -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt $cutoff } |
    ForEach-Object {
      try { Remove-Item -LiteralPath $_.FullName -Force -ErrorAction Stop; $removed++ }
      catch { Write-Warning "could not remove $($_.FullName): $($_.Exception.Message)" }
    }
}
Write-Host "[clean-logs] removed $removed file(s) older than $RetentionDays day(s) under runtime\logs + logs."
