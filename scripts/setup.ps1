<#
.SYNOPSIS
  Max Agency one-command onboarding (v1.1) -- make a GitHub repo ready for the gate.

.DESCRIPTION
  Implements the SETUP.md checklist for a target repo:
    1. Verifies the vendor CLIs are present/authenticated (gh, python, codex, claude, wsl->hermes).
    2. Creates the full gate label set on the repo (idempotent).
    3. Registers the gate as a single hidden Windows Scheduled Task (the only scheduled job).

  Safe + idempotent: re-running updates labels in place and re-registers the task. The gate
  does nothing until a human adds the `AI` label to an issue (the opt-in + kill-switch), so a
  freshly-onboarded repo with no `AI` issues is a zero-cost no-op.

.EXAMPLE
  pwsh scripts/setup.ps1 -Repo owner/repo
.EXAMPLE
  # First test on a live repo: let the CTO approve, but hold every merge for a human.
  pwsh scripts/setup.ps1 -Repo owner/repo -NoAutoMerge
.EXAMPLE
  # Labels only, don't touch the scheduler:
  pwsh scripts/setup.ps1 -Repo owner/repo -NoTask
#>
param(
  [Parameter(Mandatory = $true)][string]$Repo,
  [ValidateSet("dry-run", "deterministic-only", "dispatch-enabled")][string]$Mode = "dispatch-enabled",
  [switch]$NoAutoMerge,
  [int]$IntervalMinutes = 5,
  [string]$ScopeLabel = "AI",
  [string]$CoderModel,                 # per-repo coder model (else the gate default from gate/models.env)
  [switch]$NoTask,
  [string]$RepoRoot
)

$ErrorActionPreference = "Stop"
if (-not $RepoRoot) {
  $scriptDir = if ($PSScriptRoot) { $PSScriptRoot }
               elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath }
               else { (Get-Location).Path }
  $RepoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
}

function Say($msg) { Write-Host "[setup] $msg" }
function Ok($msg)  { Write-Host "[ ok ] $msg" -ForegroundColor Green }
function Warn($msg){ Write-Host "[warn] $msg" -ForegroundColor Yellow }

Say "Onboarding $Repo (mode=$Mode, scope='$ScopeLabel')"

# -- 1. Verify vendor CLIs ----
Say "Checking CLIs..."
function Have($name) { [bool](Get-Command $name -ErrorAction SilentlyContinue) }

if (Have gh) {
  $auth = (gh auth status 2>&1) -join "`n"
  if ($auth -match "Logged in") { Ok "gh authenticated" } else { Warn "gh present but not authenticated -- run: gh auth login" }
} else { throw "gh (GitHub CLI) not found on PATH -- required. Install: https://cli.github.com" }

if (Have python) { Ok "python present" } else { throw "python not found on PATH -- required to run the gate." }
if (Have codex)  { Ok "codex present (orchestrator: triage + kickoff expansion)" } else { Warn "codex not found -- triage/expand will no-op until installed (npm i -g @openai/codex)." }
if (Have claude) { Ok "claude present (architect + CTO)" } else { Warn "claude not found -- architect/CTO will no-op until installed." }
$hermes = (wsl.exe -e bash -lc "command -v hermes" 2>$null)
if ($hermes) { Ok "wsl->hermes present (coder)" } else { Warn "wsl->hermes not found -- coder dispatch will no-op until installed in WSL." }

# -- 2. Create the gate label set (idempotent) ----
Say "Creating gate labels on $Repo..."
$labels = @(
  @{ name = $ScopeLabel;       color = "1D76DB"; desc = "Max Agency: opt this issue in to the gate (the on-switch + kill-switch)" },
  @{ name = "role:architect";  color = "5319E7"; desc = "Gate: architect lane (turns a brief into a plan)" },
  @{ name = "role:coder";      color = "0E8A16"; desc = "Gate: coder lane (implements + opens a PR)" },
  @{ name = "role:cto";        color = "B60205"; desc = "Gate: CTO lane (reviews the PR)" },
  @{ name = "backlog";         color = "FBCA04"; desc = "Gate: waiting on dependencies" },
  @{ name = "ready";           color = "0E8A16"; desc = "Gate: ready to dispatch" },
  @{ name = "in-progress";     color = "FBCA04"; desc = "Gate: work in progress" },
  @{ name = "plan-ready";      color = "5319E7"; desc = "Gate: plan awaiting owner approval (reply APPROVE / CHANGES:)" },
  @{ name = "kickoff";         color = "1D76DB"; desc = "Gate: approved plan to expand into task issues" },
  @{ name = "needs-human";     color = "D93F0B"; desc = "Gate: parked for a human" }
)
foreach ($l in $labels) {
  gh label create $l.name --repo $Repo --color $l.color --description $l.desc --force 2>&1 | Out-Null
  if ($LASTEXITCODE -eq 0) { Ok "label $($l.name)" } else { Warn "label $($l.name) -- gh returned $LASTEXITCODE" }
}

# -- 3. Create the per-project Max_AgencyConfig in the project repo (create-only) ----
Say "Ensuring Max_AgencyConfig exists in $Repo..."
# A 404 here is normal (file not created yet). Under $ErrorActionPreference='Stop' a failing
# native command (gh) surfaces its stderr as a terminating error, so wrap it in try/catch.
$cfgPresent = $false
try {
  gh api "repos/$Repo/contents/Max_AgencyConfig" 1>$null 2>$null
  $cfgPresent = ($LASTEXITCODE -eq 0)
} catch { $cfgPresent = $false }
if ($cfgPresent) {
  Ok "Max_AgencyConfig already present (left as-is; edit it in the repo to change models)"
} else {
  $coderDefault = if ($CoderModel) { $CoderModel } else { "xiaomi/mimo-v2.5" }
  $cfg = @"
# ============================================================================
#  Max_AgencyConfig -- per-project model settings for the Max Agency gate.
#  Lives in THIS repo's root. The gate reads it each run and uses these models
#  for THIS project only -- Max Agency itself is never modified. Edit a value,
#  commit, and the next gate run uses it. Test first:  check_model.py <role> --model <id>
#
#  Each role uses a FIXED provider (set by the tool that runs it), so the id
#  FORMAT differs per field -- copy from the matching list below. Keys live with
#  the provider (OpenRouter key in ~/.hermes/.env; codex login; claude login).
# ============================================================================

GATE_CODER_MODEL=$coderDefault
GATE_TRIAGE_MODEL=gpt-5.4-mini
GATE_ARCHITECT_MODEL=opus
GATE_CTO_MODEL=opus

# ---- GATE_CODER_MODEL options (hermes -> OpenRouter; always "provider/model";
#      verify exact slug at https://openrouter.ai/models -- check_model.py validates):
#   xiaomi/mimo-v2.5              # strong coder (default)
#   anthropic/claude-sonnet-4.6  # excellent writer -- good for prose/book repos
#   anthropic/claude-opus-4.8    # top quality, higher cost
#   openai/gpt-5.4               # strong all-rounder
#   google/gemini-2.5-pro        # long-context all-rounder
#   deepseek/deepseek-v3.2       # cheap, capable
#   qwen/qwen3-coder             # budget coder
#   x-ai/grok-4                  # all-rounder
#   meta-llama/llama-4-maverick  # open-weight
#   mistralai/mistral-large-2    # open-weight
#
# ---- GATE_TRIAGE_MODEL options (codex CLI / OpenAI auth):
#   gpt-5.4-mini                 # cheap, default (verified accepted)
#   gpt-5.4                      # stronger, pricier
#
# ---- GATE_ARCHITECT_MODEL / GATE_CTO_MODEL options (claude CLI / Anthropic auth):
#   opus                         # latest Opus (default)
#   sonnet                       # faster / cheaper
#   haiku                        # cheapest
#   claude-opus-4-8              # pin a specific version
#   claude-sonnet-4-6
# ============================================================================
"@
  $b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($cfg))
  try {
    gh api "repos/$Repo/contents/Max_AgencyConfig" -X PUT -f "message=Add Max_AgencyConfig (Max Agency per-project model settings)" -f "content=$b64" 1>$null 2>$null
    if ($LASTEXITCODE -eq 0) { Ok "created Max_AgencyConfig in $Repo (coder=$coderDefault)" }
    else { Warn "could not create Max_AgencyConfig (gh returned $LASTEXITCODE)" }
  } catch { Warn "could not create Max_AgencyConfig: $($_.Exception.Message)" }
}

# -- 4. Register the single gate scheduled task ----
if ($NoTask) {
  Say "Skipping task registration (-NoTask). Run the gate manually with:"
  Write-Host "    python `"$RepoRoot\gate\gate.py`" --repo $Repo --mode $Mode --scope-label $ScopeLabel"
} else {
  Say "Registering the gate scheduled task..."
  $reg = Join-Path $RepoRoot "scripts\register-gate-task.ps1"
  $regArgs = @{ Repo = $Repo; Mode = $Mode; IntervalMinutes = $IntervalMinutes; ScopeLabel = $ScopeLabel; RepoRoot = $RepoRoot }
  if ($NoAutoMerge) { $regArgs.NoAutoMerge = $true }
  & $reg @regArgs
}

Write-Host ""
Ok "Setup complete for $Repo."
Write-Host "Next: open a GitHub issue describing the work, add the '$ScopeLabel' label, and the gate takes it from there."
Write-Host "      (Fuzzy/multi-step -> architect: it posts a plan; reply 'APPROVE' or 'CHANGES: ...'. Small/clear -> straight to the coder.)"
if ($Mode -eq "dispatch-enabled" -and -not $NoAutoMerge) {
  Warn "auto-merge is ON. For a first run on a live repo consider re-running with -NoAutoMerge."
}
