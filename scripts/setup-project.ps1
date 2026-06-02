[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Repo,
  [string]$ProjectTitle = "Agency Project"
)

$ErrorActionPreference = "Stop"

$labels = @(
  @{ name="assigned:claude-code"; color="1f77b4"; description="Pick up by Claude Code (Sonnet 4.6)" },
  @{ name="assigned:hermes";      color="d62728"; description="Pick up by Hermes (GPT-5-Codex)" },
  @{ name="phase:1";              color="9467bd"; description="Phase 1" },
  @{ name="phase:2";              color="9467bd"; description="Phase 2" },
  @{ name="phase:3";              color="9467bd"; description="Phase 3" },
  @{ name="phase:4";              color="9467bd"; description="Phase 4" },
  @{ name="ready";                color="2ca02c"; description="Dependencies met, ready for pickup" },
  @{ name="in-progress";          color="ff7f0e"; description="A coder is working on it" },
  @{ name="review";               color="17becf"; description="PR open, awaiting CTO review" },
  @{ name="blocked";              color="7f7f7f"; description="Cannot proceed" },
  @{ name="escalate";             color="e377c2"; description="Needs human attention" },
  @{ name="task";                 color="cccccc"; description="Standard agency task" }
)

foreach ($l in $labels) {
  try {
    gh label create $l.name --repo $Repo --color $l.color --description $l.description 2>$null
    Write-Information "Created label $($l.name)" -InformationAction Continue
  } catch {
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
