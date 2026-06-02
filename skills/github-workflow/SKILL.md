---
name: github-workflow
when_to_use: Any time you create a branch, commit, open a PR, review, or merge — i.e. every interaction with the repo.
applies_to: [orchestrator, coder, cto]
description: Branch-per-issue, draft PR with CI gate, independent CTO review, PR-driven merge. Never push trunk.
version: 1.0.0
license: MIT
metadata:
  hermes:
    tags: [max-agency, github, workflow, cicd]
---

# GitHub Workflow

Everything flows through issues, branches, draft PRs, CI, and CTO-approved merges. The trunk is protected; no agent pushes to it.

## When to Use

- Before starting any task — to verify branch, labels, and assignment.
- When opening a PR — to set draft state and trigger CI.
- When merging — to confirm green CI, CTO approval, and clean up.

## Procedure

### Starting a task (coder)

1. Confirm you are **not** on `main`. Run `git branch`.
2. The issue must already exist with one `assigned:<agent>` label, one `phase:<n>` label, and status `in-progress` (Orchestrator sets these on dispatch).
3. Use the worktree the Orchestrator created. Branch name is `phase-<n>/<issue-#>-<slug>`.
4. Post a pickup comment on the issue (identity block per `docs/AMA.md §1` plus `"Picked up by <agent>"`).

### During work

1. Commit early and often. Format from `CODING_STANDARDS.md §9`:
   ```
   <phase-id>/<issue-#>: <imperative subject>
   ```
   Body explains *why*, not *what*.
2. Push regularly:
   ```
   git push -u origin phase-<n>/<issue-#>-<slug>   # first push
   git push                                          # subsequent
   ```
3. Run lint, format, type-check, full tests locally before every push. CI is a backstop, not your first line of defence.

### Opening a pull request

1. Open as **draft**. Title matches the commit format. Body uses `.github/pull_request_template.md` with `Closes #<n>`.
2. Confirm CI is queued. If GitHub Actions did not start, stop and investigate — do not proceed.
3. Move the issue to `review`. Orchestrator routes to CTO.

### CI and quality gates

1. CI must be green: tests, lint, type-check, build, secret scan.
2. If CI fails, fix locally and push. CI re-runs on push.
3. Never force-past failures. Never skip hooks.
4. Once green, exit draft (mark "ready for review").

### CTO review

1. Reviewer must be a different agent instance than the author (`docs/AMA.md §2` and §7.1).
2. CTO returns one of three verdicts per `agents/cto.md`. The author responds:
   - `APPROVED` → Orchestrator requests human merge via Telegram.
   - `CHANGES REQUIRED` → author addresses each item; pushes; CI re-runs; re-request review.
   - `ESCALATE TO HUMAN` → Orchestrator forwards.
3. Cap: 2 rounds on a merge review. After round 2 → escalate.

### Merging

1. Pre-merge checks:
   - CI green.
   - CTO `APPROVED`.
   - Branch up to date with `main` (rebase if behind).
   - No unresolved review comments.
2. **Merging is a PR action, never a local push.** Use the GitHub merge button or merge queue. Never `git checkout main && git merge`. Never `git push origin main`.
3. Prefer **squash** for many small commits; **merge commit** when preserving history matters (rare).
4. Delete the branch after merge:
   ```
   git branch -d phase-<n>/<issue-#>-<slug>
   git push origin --delete phase-<n>/<issue-#>-<slug>
   ```
5. Confirm the issue auto-closed (linked via `Closes #<n>`). Orchestrator runs `scripts/rebuild-state.ps1` to refresh `State.md`.

### Rebase to keep current

If your branch falls behind `main`:

```
git fetch origin
git rebase origin/main
git push --force-with-lease origin phase-<n>/<issue-#>-<slug>
```

Always `--force-with-lease`, never `-f`. Lease refuses the push if someone else has touched the branch in the meantime.

## Pitfalls

- **Pushing to `main`.** Branch protection blocks it, but never try. Merging is a PR action.
- **Plain `--force`.** Use `--force-with-lease`. Always.
- **Merging without CTO approval.** The CTO label is the gate. No exceptions.
- **Self-review.** Author and reviewer must be different instances (`docs/AMA.md §7.1`).
- **Stale branch merged anyway.** Rebase first if behind.
- **Skipping the CI gate.** A red check signals a real problem; don't retry blindly.
- **Inventing labels.** The label set is fixed (`docs/AMA.md §3`). Propose changes via an issue, don't unilaterally add.

## Verification

- `git branch` — not on `main`.
- `git log --oneline -5` — atomic commits in `<phase-id>/<issue-#>: ...` format.
- PR is draft until CI green, then ready for review.
- Issue has exactly one `assigned:*` and one `phase:*` label.
- CI green, CTO `APPROVED`.
- After merge: branch deleted local and remote, issue closed, `State.md` regenerated.
- `git log main -1` shows the merge came from a PR, not a direct push.
