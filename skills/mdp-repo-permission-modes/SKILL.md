---
name: mdp-repo-permission-modes
description: Use when setting or enforcing repository permission mode for MDP-managed work, including local edits, commits, pushes, PRs, deploys, and privileged actions.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [mdp, permissions, git, github, safety]
    related_skills: [mdp-project-kickoff, mdp-decision-gates, mdp-file-safety]
---

# MDP Repository Permission Modes

## Overview

Every MDP-managed project declares a permission mode at kickoff. The mode defines what agents can do without asking again. This prevents accidental commits, pushes, remote actions, deploys, or privileged repository changes.

Permission mode belongs near the top of project context and should be repeated in risky task prompts.

## When to Use

Use this skill when:

- Starting or importing an MDP project.
- Changing files, commits, branches, PRs, remotes, settings, or deployments.
- Briefing workers that may use git or GitHub.
- Deciding whether Max approval is needed before an action.
- Recovering from unclear repository authority.

## Modes

- Mode 0: read-only inspection.
- Mode 1: local file edits allowed, no commits.
- Mode 2: local commits allowed, no push.
- Mode 3: remote actions allowed, such as push or PR within approved limits.
- Mode 4: privileged actions allowed, such as merge, force-push, branch deletion, repo settings, repo creation, or deploy.

## Role Guidance

- Operator: usually max Mode 2.
- PA / Orchestrator: can coordinate, usually max Mode 2 unless explicitly approved.
- CTO: usually max Mode 3 for technical delivery.
- COO: approval authority, usually max Mode 3 if acting directly.
- CFO: only for finance/cost related repo or billing changes.
- Human Owner: final override.

## Hard Gates

Always escalate before:

- Creating repositories.
- Force-pushing.
- Deleting branches with shared work.
- Merging to protected branches.
- Changing repo settings, permissions, secrets, or CI/CD deployment credentials.
- Deploying to production or live systems.
- Touching GitHub when the project pointer says not to.

## Worker Prompt Requirements

Any worker with repository access should receive:

- Current permission mode.
- Allowed actions.
- Forbidden actions.
- Branch/worktree boundary.
- Commit/push/PR policy.
- Rollback expectation.
- Verification required.

## Common Pitfalls

1. **Assuming local edit permission includes commit permission.** Mode 1 does not allow commits.
2. **Assuming commit permission includes push permission.** Mode 2 does not allow push.
3. **Treating PR creation as harmless.** PRs are remote actions and require Mode 3.
4. **Letting workers decide permission mode.** They enforce it. They do not invent it.
5. **Forgetting project-specific restrictions.** A project pointer can be stricter than the mode.

## Verification Checklist

- [ ] Current permission mode is known before repository action.
- [ ] Worker prompts include allowed and forbidden git/GitHub actions.
- [ ] No commits, pushes, PRs, merges, deploys, or settings changes exceeded the mode.
- [ ] Hard gates were escalated.
- [ ] Final report states any repository actions taken or explicitly avoided.
