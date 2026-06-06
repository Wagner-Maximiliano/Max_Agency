[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Repo,
  [Parameter(Mandatory=$true)][string]$AgencyPath,
  [string]$PromptPath
)

# run-tick.ps1 — one Claude Code routine tick with model-per-label enforcement.
#
# Why this exists: the PLAN.md model roster assigns each task a cost tier via an
# `assigned:claude-<model>` label (haiku/sonnet/opus). A bare `claude --print`
# runs whatever the CLI default is, so the roster was cosmetic. This launcher
# peeks the queue, finds the model the next claimable issue demands, and starts
# Claude with the matching `--model`. Single-instance scheduling means the peek
# and the routine's own lowest-issue-number pick agree.

$ErrorActionPreference = "Stop"

if (-not $PromptPath) { $PromptPath = Join-Path $PSScriptRoot "poll-and-pickup.md" }
if (-not (Test-Path $PromptPath)) { throw "poll-and-pickup.md not found at $PromptPath" }

$claudeCmd = (Get-Command claude -ErrorAction SilentlyContinue)
if (-not $claudeCmd) { throw "Claude Code CLI 'claude' not found on PATH." }

# --- Phase 1: peek the queue, decide the model -------------------------------
# Lowest-numbered open issue that is in-progress, has a role:* label, an
# assigned:claude-* label, and NO assignee (unclaimed). Mirrors the routine's
# own selection in poll-and-pickup.md steps 1-3.
$modelAlias = "sonnet"   # default if nothing claimable (routine will exit NO_WORK)
try {
  $raw = & gh issue list --repo $Repo --label "in-progress" --state open `
            --json number,labels,assignees --limit 50 2>$null | ConvertFrom-Json
  $claimable = $raw |
    Where-Object { $_.assignees.Count -eq 0 } |
    Where-Object { ($_.labels.name) -match '^role:' } |
    Where-Object { ($_.labels.name) -match '^assigned:claude-' } |
    Sort-Object number
  if ($claimable) {
    $next = $claimable[0]
    $assignedLabel = ($next.labels.name | Where-Object { $_ -like 'assigned:claude-*' } | Select-Object -First 1)
    switch ($assignedLabel) {
      'assigned:claude-haiku'  { $modelAlias = 'haiku' }
      'assigned:claude-sonnet' { $modelAlias = 'sonnet' }
      'assigned:claude-opus'   { $modelAlias = 'opus' }
      default                  { $modelAlias = 'sonnet' }
    }
    Write-Information "run-tick: next claimable issue #$($next.number) -> $assignedLabel -> --model $modelAlias" -InformationAction Continue
  } else {
    Write-Information "run-tick: no claimable claude-* issue; launching default model (routine will likely exit NO_WORK)" -InformationAction Continue
  }
} catch {
  Write-Information "run-tick: queue peek failed ($($_.Exception.Message)); falling back to --model $modelAlias" -InformationAction Continue
}

# --- Phase 2: substitute env vars into the prompt, run Claude with the model --
$prompt = (Get-Content $PromptPath -Raw) `
  -replace [regex]::Escape('$env:PROJECT_REPO'), $Repo `
  -replace [regex]::Escape('$env:USERPROFILE'), $env:USERPROFILE

Set-Location $AgencyPath
$env:PROJECT_REPO = $Repo
$prompt | claude --model $modelAlias --print --dangerously-skip-permissions
exit $LASTEXITCODE
