[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Repo,
  [string]$ProjectTitle = "Agency Project"
)

$ErrorActionPreference = "Stop"

$labels = @(
  # assigned:<model> — who picks up this issue
  @{ name="assigned:claude-haiku";  color="1f77b4"; description="Pick up by Claude Haiku (fast, cheap)" },
  @{ name="assigned:claude-sonnet"; color="4e92d8"; description="Pick up by Claude Sonnet (balanced)" },
  @{ name="assigned:claude-opus";   color="2c5f9e"; description="Pick up by Claude Opus (complex/CTO tasks)" },
  @{ name="assigned:hermes-coder";  color="d62728"; description="Pick up by Hermes coder profile" },
  # role:<role> — which agent file / behavior to load
  @{ name="role:architect";         color="8c564b"; description="Architect role (PLAN.md authoring)" },
  @{ name="role:cto";               color="e377c2"; description="CTO role (PR review + verdict)" },
  @{ name="role:coder";             color="bcbd22"; description="Coder role (implementation)" },
  # phase:<N> — project phase
  @{ name="phase:0";                color="9467bd"; description="Phase 0" },
  @{ name="phase:1";                color="9467bd"; description="Phase 1" },
  @{ name="phase:2";                color="9467bd"; description="Phase 2" },
  @{ name="phase:3";                color="9467bd"; description="Phase 3" },
  @{ name="phase:4";                color="9467bd"; description="Phase 4" },
  @{ name="phase:5";                color="9467bd"; description="Phase 5" },
  @{ name="phase:6";                color="9467bd"; description="Phase 6" },
  @{ name="phase:7";                color="9467bd"; description="Phase 7" },
  # state — lifecycle position (orchestrator manages transitions)
  @{ name="kickoff";                color="f7b731"; description="Kickoff issue — triggers PLAN.md parsing" },
  @{ name="planned";                color="f0a500"; description="Kickoff claimed, issues being created" },
  @{ name="backlog";                color="aec7e8"; description="Waiting on dependencies" },
  @{ name="ready";                  color="2ca02c"; description="Dependencies met, ready for pickup" },
  @{ name="in-progress";            color="ff7f0e"; description="A coder is working on it" },
  @{ name="review";                 color="17becf"; description="PR open, awaiting CTO review" },
  @{ name="blocked";                color="7f7f7f"; description="Cannot proceed — needs human" }
)

foreach ($l in $labels) {
  gh label create $l.name --repo $Repo --color $l.color --description $l.description 2>$null
  if ($LASTEXITCODE -eq 0) {
    Write-Information "Created label $($l.name)" -InformationAction Continue
  } else {
    gh label edit $l.name --repo $Repo --color $l.color --description $l.description | Out-Null
    Write-Information "Updated label $($l.name)" -InformationAction Continue
  }
}

# Branch protection on main
$owner = $Repo.Split("/")[0]
$name  = $Repo.Split("/")[1]
$body = @'
{
  "required_status_checks": null,
  "enforce_admins": false,
  "required_pull_request_reviews": { "required_approving_review_count": 0 },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
'@
$tmp = New-TemporaryFile
$body | Out-File -FilePath $tmp -Encoding utf8
try {
  gh api -X PUT "repos/$Repo/branches/main/protection" --input $tmp | Out-Null
  Write-Information "Branch protection enabled on main" -InformationAction Continue
} catch {
  Write-Warning "Could not set branch protection (main may not exist yet): $_"
}
Remove-Item $tmp -Force

Write-Information "Project setup complete for $Repo" -InformationAction Continue
Write-Information "Next: create a Project board on github.com with columns: Backlog, Ready, In-progress, Review, Done, Blocked" -InformationAction Continue
