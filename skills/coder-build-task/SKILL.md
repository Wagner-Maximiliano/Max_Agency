---
name: coder-build-task
when_to_use: Implementing a single GitHub issue assigned to you — from worktree pickup to draft PR.
applies_to: [coder]
description: Execute one task in-scope, write meaningful tests, and open a draft PR with a structured result payload.
version: 1.0.0
license: MIT
metadata:
  hermes:
    tags: [max-agency, build, coding, task-driven]
---

# Build One Task to Acceptance

Implement exactly one assigned issue. Stay in scope. Write tests that actually test. Open a draft PR. Report success or failure in the structured format below.

## When to Use

- An issue is in `in-progress` with `assigned:<your-agent>` and a worktree exists at `worktrees/<your-agent>/<issue-#>-<slug>/`.
- You have read the issue's acceptance criteria, dependencies, and rollback plan.

## Procedure

### Stage 1 — Orient

1. Confirm:
   - Issue is `in-progress` and assigned to you.
   - Branch is `phase-<n>/<issue-#>-<slug>`, branched from `main`.
   - You are inside your assigned worktree.
2. Read the issue's **Acceptance criteria** and **Rollback** sections in full. Restate them to yourself as a checklist.
3. Skim the files you expect to touch. Note repo conventions: lint config, test runner, naming patterns.
4. If the acceptance criteria are ambiguous, post **one** clarifying comment on the issue and stop. Do not guess.

### Stage 2 — Implement in scope

1. The acceptance criteria are the boundary. Do not:
   - Refactor unrelated code.
   - Add speculative features.
   - Change interfaces beyond what the criteria require.
   - Optimize without a profiled reason.
2. Write **why-comments only**. The code shows *what*; comments explain non-obvious *why*. No `i += 1 // increment i`.
3. Commit incrementally per `CODING_STANDARDS.md §9`:
   ```
   git commit -m "<phase-id>/<issue-#>: <imperative subject>"
   ```
4. If the task involves schema or data migrations: make them reversible, document data shape, flag any data-loss risk in the PR description.

### Stage 3 — Test alongside the code

1. For each acceptance criterion, write a test that asserts the observable behaviour.
2. Cover edge cases: empty/null, boundary, concurrent (if applicable), error paths.
3. Test behaviour, not implementation. Mock only external dependencies (network, clock, FS for unit tests). Never mock the code under test.
4. No sleeps. If a test is flaky on timing, fix the root cause.
5. Run the full local suite before each push. Red = do not push.

### Stage 4 — Self-review

Run the Task Completion Checklist from the issue:

- [ ] Each acceptance criterion has a code change.
- [ ] Each acceptance criterion has a test that fails when the code is broken.
- [ ] Lint, format, type-check all pass.
- [ ] Build passes.
- [ ] No secrets, no `print`/`console.log`, no commented-out code.
- [ ] Docs updated if behaviour changed.

If any box is unchecked, fix before opening the PR.

### Stage 5 — Open a draft PR

1. Push:
   ```
   git push -u origin phase-<n>/<issue-#>-<slug>
   ```
2. Open a **draft** PR. Title: `<phase-id>/<issue-#>: <imperative subject>`. Body uses `.github/pull_request_template.md`. Include `Closes #<n>` and mark each acceptance criterion checked.
3. Move the issue to `review`.
4. Do **not** request review yourself — Orchestrator routes to CTO.

### Stage 6 — Report result

Post one comment on the issue with this exact JSON in a fenced block:

```json
{
  "pr_url": "https://github.com/.../pull/<n>",
  "summary": "one-line what was built",
  "tests_added": ["test_x", "test_y"],
  "acceptance_criteria_met": ["criterion 1", "criterion 2"],
  "out_of_scope_notes": ["new issue #<n> opened for unrelated refactor"],
  "blocked": false,
  "blocker_reason": null
}
```

If blocked after honest attempts (see `agents/coder.md` Failure protocol):

```json
{
  "pr_url": null,
  "summary": null,
  "tests_added": [],
  "acceptance_criteria_met": [],
  "out_of_scope_notes": [],
  "blocked": true,
  "blocker_reason": "<what failed, what you tried, what you suspect>"
}
```

## Pitfalls

- **Scope creep.** "While I'm here, let me refactor X." → open a separate issue, note it under `out_of_scope_notes`, move on.
- **Partial implementation.** Happy path works, edge case doesn't. Re-read criteria before pushing.
- **Tests that don't test.** If breaking the implementation doesn't break the test, the test is wrong.
- **Confidence without evidence.** "It should work" is not a verification step. Run the suite.
- **Skipping lint/format.** CI will catch you. Local is faster.

## Verification

- Branch matches `phase-<n>/<issue-#>-<slug>`, not `main`.
- All acceptance criteria check off against code + test.
- Local suite green: tests, lint, type-check, build.
- Draft PR open, title and body conformant, issue moved to `review`.
- Result JSON posted as a comment.
