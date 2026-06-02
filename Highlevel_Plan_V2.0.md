# Max Agency — High-Level Plan V2.0

## Core principles

1. **GitHub is the single source of truth.** Issues, Projects, branches, PRs. `State.md` is a generated snapshot, never the source.
2. **Every role is restartable from GitHub state alone.** No agent holds in-memory context that isn't recoverable.
3. **One task = one issue = one worktree = one branch = one agent.** No shared writes.
4. **Objective gates, not self-reported confidence.** Pass/fail on tests, schema, checklist — never "I'm 98% sure".
5. **Bounded loops.** Every back-and-forth has a max retry count. Hit the cap → escalate to human via Telegram.
6. **Human in the loop at three points only:** initial brief, plan approval, escalation. Everything else is autonomous.

---

## Roles

### Architect — Opus 4.8
- Talks to the human. Asks up to 5 clarifying questions, batched.
- Produces `PLAN.md`: goals, milestones, phases, tasks with dependencies.
- Sends plan to CTO for review. Revises up to 3 times. If still rejected → escalate to human.
- Final plan is committed to repo and approved by human (one explicit ack) before work starts.

### CTO — Opus 4.8
- Reviews and approves/rejects the plan against the **Plan Acceptance Checklist** (see below).
- Approves/rejects merges to `main` against the **Merge Acceptance Checklist**.
- Independent from Architect — never authors plans.
- On any decision they cannot resolve in 1 round with the Orchestrator → escalate to human.

### Orchestrator — GPT-5 class
- Reads `PLAN.md`, creates GitHub issues, assigns to coders.
- Monitors issue status, opens PRs when phase complete, requests CTO review.
- Cold-start safe: on restart, rebuilds full state from GitHub issues + branches.
- Identifies parallelizable tasks (no dep overlap, no file overlap) and dispatches concurrently.
- Watchdog: any issue in `in-progress` with no commit in 30 min → reassign or escalate.

### Coders — GPT-5-Codex & Sonnet 4.6
- Pick up issues assigned to them via label `assigned:<model>`.
- Work in their own worktree on their own branch.
- On task failure (tests red, build broken) retry up to 2 times. Third failure → request cross-provider review (GPT ↔ Sonnet) which produces a written diagnosis comment on the issue. Fourth failure → escalate to Orchestrator.

---

## Task structure (GitHub issue template)

```
Title: <verb-led, <60 chars>
Phase: <phase-id>
Depends-on: #<issue>, #<issue>
Assigned-model: <gpt-5-codex | sonnet-4.6>
Environment: <hermes | claude-code>

## Why
<1-2 sentences>

## Acceptance criteria
- [ ] <objective, testable>
- [ ] <objective, testable>

## Proposed approach
<short>

## Rollback
<how to undo if merged and broken>
```

Status is tracked by GitHub Project columns: `Backlog → Ready → In-progress → Review → Done → Blocked`.

---

## Coordination contract (Hermes ↔ Claude Code)

- **Locking:** assignment of a GitHub issue = the lock. Only the assigned agent may push to that branch.
- **Branch naming:** `phase-<n>/<issue-number>-<slug>`.
- **Worktrees:** created on assignment, deleted on issue close.
- **Cross-environment handoff:** only via merged PR. No two agents share a working tree.
- **Conflict resolution:** if a PR conflicts on rebase, the issue returns to Orchestrator, who decides re-sequencing.

---

## Gates (replace "confidence %")

### Plan Acceptance Checklist (CTO signs off)
- [ ] Each phase has measurable acceptance criteria
- [ ] Every task has dependencies declared
- [ ] Rollback exists for every irreversible task
- [ ] Estimated token/$ budget is within project cap
- [ ] Human goal restated and matches brief

### Task Completion Checklist (coder self-checks before marking Review)
- [ ] Acceptance criteria met
- [ ] Tests added and passing
- [ ] Lint/type checks clean
- [ ] No secrets committed

### Merge Acceptance Checklist (CTO signs off)
- [ ] All task checklists green
- [ ] CI green on the PR
- [ ] No unresolved review comments
- [ ] State snapshot regenerated

---

## Resilience

- **State recovery:** `bin/rebuild-state` reads GitHub and regenerates `State.md`. Any role can be killed and restarted.
- **Heartbeat:** Orchestrator pings every 5 min to a status file. Missing 3 pings → external watchdog restarts it.
- **Failure escalation path:** retry (bounded) → cross-provider review → Orchestrator → CTO → human via Telegram.
- **Budget guard:** per-project token/$ cap. At 80% used, Orchestrator notifies human. At 100%, all work pauses pending human ack.

---

## Standards

See `CODING_STANDARDS.md` for full rules. Agency-specific deltas from common practice:

- Every task on its own worktree and branch — no exceptions.
- Secrets via environment only; commit hook rejects anything resembling a key.
- Commit messages: `<phase-id>/<issue-#>: <subject>`.
- Logging via the shared logger; no `print`/`console.log` in committed code.

---

## Frameworks

- **MDP** (Model Development Protocol): defined in `docs/MDP.md`.
- **AMA** (Agent Multi-Agent protocol): defined in `docs/AMA.md`.

Both are read by every agent on startup.

## Skills

Reusable instructions, recipes, and capability descriptions live in `skills/` as one `.md` file per skill with frontmatter (`name`, `when_to_use`, `applies_to`). All agents are required to discover skills on every task — Architect scans before drafting `PLAN.md`, CTO checks coverage during review, Orchestrator lists relevant skills in dispatch comments, and Coders must load matching skills before writing code. See `skills/README.md` for the format.

## Runtime split

- **Hermes side** — Two isolated Hermes profiles host non-Anthropic roles, both via OpenRouter:
  - `orchestrator` profile → Orchestrator role, `openai/gpt-5`
  - `coder` profile → non-Anthropic Coder role, `openai/gpt-5-codex`
  Each profile has its own SOUL.md, skills, memory, and `hermes cron` polling job.
- **Anthropic side** — Claude Code Windows app driven by Windows Task Scheduler. One scheduled task polls GitHub for issues labelled `assigned:claude-*` and picks up Architect, CTO, or Anthropic Coder work depending on the label.
- **Coordination** — GitHub issues + labels. There is no inter-runtime RPC; everything flows through the issue tracker.

## Repository layout

```
agents/                Role contracts (architect, cto, orchestrator, coder)
docs/                  Laws, Policies, Protocols, Rules (MDP, AMA, ...)
skills/                Reusable on-demand instructions (one .md per skill)
hermes-config/         Hermes-native profile templates, cron jobs, poll prompts
claude-code-routine/   Task Scheduler routine for the Anthropic side
templates/             PLAN.md / State.md skeletons
scripts/               PowerShell helpers (state rebuild, project setup)
.github/               Issue template, PR template, CI workflow
Human_Runbook.md       The only human-facing doc
```
