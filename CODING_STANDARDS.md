# Coding Standards

Rules that apply to all code produced by agents in this agency. Keep this file short and enforceable — if a rule can't be checked by a linter, a test, or a reviewer in under a minute, it doesn't belong here.

---

## 1. Style and formatting

Follow the language's official style guide. Do not invent house style.

| Language    | Style guide | Formatter / Linter        |
|-------------|-------------|---------------------------|
| Python      | PEP 8       | `ruff` + `black`          |
| JavaScript  | Airbnb      | `eslint` + `prettier`     |
| TypeScript  | Airbnb-TS   | `eslint` + `prettier`     |
| Go          | Effective Go| `gofmt` + `golangci-lint` |
| Shell       | Google      | `shellcheck`              |

Formatter must run pre-commit. CI rejects unformatted code.

---

## 2. Naming

- Descriptive names. `totalAmount`, not `x`. `fetchUserById`, not `getU`.
- Convention per language: `snake_case` for Python, `camelCase` for JS/TS, `PascalCase` for types/classes.
- No abbreviations unless industry-standard (`url`, `id`, `db` ok; `usrMgr` not ok).
- Booleans read as questions: `isReady`, `hasAccess`, `canMerge`.

---

## 3. Structure

- **Single Responsibility:** one function does one thing. If you use "and" describing it, split it.
- **Max function length:** ~50 lines. Hard cap 100. Exceed only with a reason in a comment.
- **Max file length:** ~400 lines. Split by concern.
- **Separation of concerns:** logic, I/O, and presentation in different modules.
- **No circular imports.**

---

## 4. Comments and documentation

- Public functions/classes get a docstring: purpose, params, returns, raises.
- Inline comments explain **why**, never **what**. The code shows what.
- No dead-code comments. Delete it; git remembers.
- Update docs in the same PR as the code change. Stale docs fail review.

---

## 5. Error handling

- Catch specific exceptions, never bare `except:` or `catch (e)` that swallows everything.
- Every caught error is either handled, re-raised, or logged with context.
- No empty catch blocks.
- Validate at boundaries (user input, API responses, file I/O). Trust internal calls.
- User-facing errors are actionable; internal errors include enough context to debug.

---

## 6. Logging

- Use the project logger. No `print`, no `console.log` in committed code.
- Levels: `DEBUG` (dev only), `INFO` (lifecycle events), `WARN` (recoverable issue), `ERROR` (failed operation), `CRITICAL` (system unusable).
- Log structured fields (JSON) in production paths. No PII, no secrets, no tokens.
- One log line per event. Don't spam loops.

---

## 7. Testing

- Every new function with non-trivial logic gets a unit test.
- Integration tests for anything crossing a process or network boundary.
- Tests must be deterministic. No sleeps, no real network, no real clock — use fakes.
- CI runs the full suite. Red CI blocks merge, no exceptions.
- Coverage target: 80% on changed lines. Not a religion — meaningful tests > coverage number.

---

## 8. Security

- No secrets in code, ever. Use env vars or the secret manager. Pre-commit hook rejects anything matching common key patterns.
- Sanitize all external input (SQL, shell, HTML, path).
- Parameterized queries only. No string-concatenated SQL.
- Dependencies pinned. Dependabot/Renovate enabled. Security patches merged within 7 days.
- No `eval`, no `exec` on dynamic input.

---

## 9. Version control

- One logical change per commit.
- Commit message format: `<phase-id>/<issue-#>: <imperative subject>`.
  - Example: `p2/#47: add retry logic to orchestrator dispatch`.
- Branch naming: `phase-<n>/<issue-#>-<slug>`.
- No force-push to shared branches. No force-push to `main`, ever.
- Rebase to keep history linear before merging.

---

## 10. Performance

- Write for clarity first. Optimize only when profiled and proven slow.
- Pick the right data structure (hash for lookup, array for order). That covers 90% of perf decisions.
- No N+1 queries. Batch DB and API calls.
- Async I/O for anything network-bound.

---

## 11. Dependencies

- Prefer the standard library. Add a dependency only when it saves real work.
- Justify any new dep in the PR description: what it gives us, what alternative was rejected.
- License check: MIT / Apache-2.0 / BSD ok. GPL/AGPL needs CTO approval.

---

## 12. Agency-specific rules (deltas from common practice)

These override or add to the above. They exist because of how the agency operates — not general best practice.

1. **One task = one worktree = one branch.** Never edit a branch you weren't assigned to.
2. **GitHub issue is the source of truth.** Update status before walking away from a task.
3. **Acceptance criteria in the issue must be checked off before requesting review.** No exceptions.
4. **Cross-provider review at failure threshold.** When a coder fails a task 3x, a coder from the other provider must review and comment before the 4th attempt.
5. **Budget awareness.** If a task is consuming >2x its estimated tokens, pause and escalate to Orchestrator before continuing.
6. **State recoverability.** Never store project state only in conversation memory. If it matters, it goes in the issue, a commit, or `State.md` (which is regenerated from GitHub).
7. **Mandatory skill discovery.** Before writing any code, scan `skills/` for entries whose `applies_to` includes your role and `when_to_use` matches the task. Load matching bodies and follow them. Skipping discovery is a violation caught in CTO review. See `skills/README.md`.

---

## Enforcement

- **Automated:** formatter, linter, type checker, secret scanner, test suite — all in pre-commit and CI.
- **Reviewer:** checks the things automation can't (naming, structure, comment quality, dep justification).
- **CTO:** spot-checks merged PRs weekly. Repeated violations → standard gets tightened or the rule gets dropped if it's not earning its keep.
