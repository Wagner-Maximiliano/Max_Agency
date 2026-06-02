# AMA — Agent-to-Agent Protocol

This document is binding on every agent. Read it before acting. It governs how agents identify themselves, hand off work, request cross-provider review, and escalate.

Source of truth for *what* to do is `PLAN.md` and the GitHub issues. This file is the protocol for *how* agents talk to each other.

---

## 1. Identity and capability announcement

Every agent action against the repo (issue comment, PR comment, commit, label change) must be attributable. Use the following on every first comment of an interaction:

```
[agent] <role>:<provider>:<model>
[profile] <hermes-profile-name | claude-routine>
[issue] #<n>   [branch] <branch>
```

Examples:

```
[agent] coder:hermes:openai/gpt-5-codex
[profile] coder
[issue] #42   [branch] phase-2/42-add-retry
```

```
[agent] cto:anthropic:claude-opus-4.8
[profile] claude-routine
[issue] #42   [branch] phase-2/42-add-retry
```

Agents must declare role honestly. A coder must not post as a CTO; a CTO must not author plan content.

---

## 2. Roles and authority

| Role | Authoring rights | Approval rights | Cannot |
|---|---|---|---|
| Architect | `PLAN.md`, ADRs | — | Approve own plan; merge |
| CTO | ADRs, review verdicts | Plan, merge | Author plans; write product code |
| Orchestrator | Issues, labels, `State.md` (via script) | — | Approve merges; write product code |
| Coder | Product code, tests, PR body | — | Approve own PR; merge; touch foreign worktrees |
| Human | Anything | Final on any escalation | — |

If a role boundary is unclear, prefer **less authority**, not more. Post a comment and stop.

---

## 3. Handoff via GitHub labels

Handoff is exclusively by label transition on the issue. No direct messaging between agents.

| Transition | Trigger | Next owner |
|---|---|---|
| `ready` + `assigned:<agent>` | Orchestrator dispatch | Coder picks up |
| `in-progress` | Coder posts pickup comment | Coder |
| `review` | Coder opens draft PR ready for review | CTO |
| `blocked` | Any agent hits a hard wall | Orchestrator triages |
| `escalate` | Bounded retry exhausted | Human (Telegram) |
| `phase:N` | Set at issue creation | — |

The label set is fixed. Inventing new labels mid-project is a violation — propose them via an issue in the meta-repo first.

---

## 4. Cross-provider review

When a coder fails a task **three times**, they request review from the *other provider's* coder before attempting again.

### Requesting

The blocked coder posts a single issue comment titled exactly `Cross-provider review requested` containing:

```
[agent] coder:<provider>:<model>
[attempts] 3
[acceptance-criteria-met]
- [x] criterion 1
- [ ] criterion 2 — failing test: <name>
- [ ] criterion 3 — not attempted

[what-i-tried]
1. <approach + outcome>
2. <approach + outcome>
3. <approach + outcome>

[suspected-cause]
<one paragraph>

[branch] <branch>
[last-commit] <sha>
```

Then sets label `blocked` and unassigns themselves.

### Delivering

Orchestrator reassigns the issue to a coder on the *other* provider with label `assigned:<other-agent>` and `cross-review`. The reviewing coder:

1. Checks out the branch, reads the diff and failing tests.
2. Posts one comment titled exactly `Cross-provider review delivered` containing:
   ```
   [agent] coder:<provider>:<model>
   [diagnosis]
   <root cause analysis, file:line specific>

   [recommended-fix]
   <concrete steps, not full code>

   [confidence] high | medium | low
   ```
3. Does **not** push code. The original coder owns the fix.

The original coder is then reassigned. On the next failure, Orchestrator escalates to human.

---

## 5. Disagreement resolution

Two cases.

### Architect ↔ CTO on plan content

Capped at **3 rounds**. Each round:

1. CTO posts `VERDICT: CHANGES REQUIRED` with specific, actionable items.
2. Architect either applies them or pushes back in one comment titled `Plan defence — round <n>` citing the specific item and the rationale.
3. CTO re-reviews.

After round 3 with no convergence, Architect sets label `escalate` and posts to Telegram with both positions and a recommendation. Human breaks the tie.

### Coder ↔ CTO on a PR

Capped at **2 rounds**. Same shape. After round 2, Orchestrator routes to human.

### Coders disagreeing during cross-provider review

Not allowed. The reviewing coder delivers a diagnosis; the original coder is not obligated to agree but **must** either:

- Apply the recommended fix (no debate in-channel), or
- Mark the issue `escalate` with both perspectives.

There is no third coder. No vote. Humans break ties.

---

## 6. Escalation chain

| Trigger | Path |
|---|---|
| Coder 4th attempt fails (post cross-review) | Coder → Orchestrator → Human |
| CTO `ESCALATE` verdict | CTO → Orchestrator → Human |
| Plan disagreement after 3 rounds | Architect → Human |
| Merge disagreement after 2 rounds | Orchestrator → Human |
| Budget at 80% | Orchestrator → Human (warning, work continues) |
| Budget at 100% | Orchestrator → Human (all work pauses) |
| Scope drift detected | Orchestrator → Architect + CTO → Human if unresolved |
| Window exhaustion across all paid vendors | Orchestrator → Human (work pauses; auto-resume on reset) |

Every escalation uses the Telegram format defined in `agents/orchestrator.md` §Escalation triggers. Always include a link to the issue.

---

## 7. Hard rules

1. **No self-review.** Author and approver must be different agent instances. Different model is preferred; same model on a different profile is the minimum.
2. **No off-protocol channels.** All inter-agent coordination is on the GitHub issue. No DMs, no shared scratchpads, no out-of-band state.
3. **No silent retries.** Every attempt is a comment on the issue. The audit trail is the protocol.
4. **No protocol bypass.** If the protocol blocks you, propose a change via an issue. Do not work around it.
5. **No identity spoofing.** Post under your real `[agent]` line. Pretending to be another role to push something through is a critical violation.
6. **Read `docs/MDP.md` and this file every cold start.** They are the laws. `PLAN.md` is the project. Skills are the tools. Don't confuse the layers.

---

## 8. Used by

- `agents/orchestrator.md` — when dispatching, monitoring, and escalating.
- `agents/coder.md` — when handing off, requesting cross-provider review, and on every failed attempt.
- `agents/architect.md` and `agents/cto.md` — when disagreeing on plan or merge content.

If this file changes, every agent must re-read it at the start of their next session.
