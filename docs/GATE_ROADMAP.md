# Max Agency — Simplification & Reliability Roadmap v3

> Durable copy of the approved roadmap (source of truth). Phase 2A is built and
> validated; see `gate/` for the implementation and `gate/README.md` for status.

## Context (why we're doing this)

Max Agency works but is hard to operate. The disease is **uncontrolled autonomy**: multiple
pollers, weak models self-selecting work, label-based races, and a methodology layer (MDP)
pretending to be runtime enforcement. The fix: one deterministic gate, GitHub as durable
state, LLMs called only when needed, one `AI` label as the human interface, MDP deleted.

**Decisions locked in:**
- Keep all **3 vendors** (Claude, Codex, OpenRouter) — multi-vendor cross-review is a strength.
- Models (**benchmarked + promoted in Phase 0**, 5/5 each): orchestrator =
  `gpt-5.4-mini` (Codex); coder = `xiaomi/mimo-v2.5` (OpenRouter); CTO + Architect = Claude Opus.
- One scheduled **deterministic gate** dispatches; workers never self-schedule.
- Single opt-in label **`AI`** = human on-switch + gate scope filter + kill-switch.
- Plan approval via GitHub comment. **Cut MDP entirely.**

**Sequencing discipline (the #1 rule):** build the new gate *beside* the old system, in small
cuts, dry-run before it has power, and **delete the old pollers only after the new flow passes
live tests**. No big-bang.

---

## Runtime principle: a deterministic gate guards every LLM call

The only scheduled thing is a **cheap deterministic gate script (no LLM)**. Its universe is
always **open issues with the configured scope label** (`AI-GATE-TEST` during 2A–2E, `AI`
from 2F onward). An LLM is woken **only** for a specific scoped issue that needs judgment.
Empty board ⇒ exit ⇒ zero cost. Removing the scope label pauses an issue.

## The issue state machine (single source of gate truth)

| Issue state (labels) | Condition | Gate action | LLM? |
|---|---|---|---|
| scope label only | no workflow labels | **triage** (classify + label) | orchestrator |
| `role:architect` | no plan yet | invoke **architect** | Claude |
| `plan-ready` | no approval comment | **wait** | — |
| `plan-ready` | owner commented `APPROVE` | create `kickoff` | — |
| `plan-ready` | owner commented `CHANGES:` | reopen architect w/ feedback | — |
| `kickoff` | exists | expand PLAN → task issues, each stamped w/ scope label | orchestrator |
| `role:coder`+`backlog` | deps closed | → `ready` | — |
| `role:coder`+`ready` | no active dispatch marker | → `in-progress` + dispatch | coder |
| `role:coder`+`in-progress` | no PR after N min | **recovery** | —/orchestrator |
| `role:cto` | PR ready, no verdict | invoke **CTO** | Claude |
| any | linked PR merged | close issue | — |
| any | `needs-human` | wait for human | — |

Unknown/conflicting state → log `unknown-state`, **no action on that issue, continue the rest**
(one corrupt issue never halts the board). *(Deferred: auto-`needs-human` for invalid combos
waits until the gate has write power.)*

## Labels (compact — whole set, no governance framework)
```
Scope:  AI-GATE-TEST (migration)  ·  AI (production, from 2F)
Role:   role:architect · role:coder · role:cto
State:  backlog · ready · in-progress · plan-ready · kickoff · needs-human
```

## Cross-cutting engineering requirements (every gate change honors these)

1. **Run lock (mandatory).** Acquire `gate.lock` (run-id + start ts) at start; release at end.
   Fresh lock held → skip (exit 0). Older than `STALE_MIN` → reclaim + warn. *Local lock is fine
   for one Windows host; if multi-host/Actions later, switch to a GitHub-based lock.*
2. **Idempotency markers — marker comments, not labels.** Machine metadata in a hidden
   `<!-- max-agency-dispatch … -->` comment (run_id, issue, role, model, attempt, status, ts).
   One marker per issue, **edited in place**; history goes to log files. "Assigned" = latest
   marker `started`/`pr-open` and not stale; "unassigned" = no/failed/stale marker. Never use a
   human assignee for dispatch state.
3. **Recovery (simplified, NOT deleted).** `in-progress` with no PR after `STUCK_MIN` → reclaim
   → retry up to `MAX_ATTEMPTS` → `needs-human` + escalate. Keep idempotent kickoff-resume.
   Remove only the claim-last dance (a single locked gate makes it unnecessary).
4. **Observability (mandatory).** One run = one correlated structured log keyed by run-id.
   **Path: `runtime/logs/gate/<run_id>.jsonl`.**
5. **Security.** Least-privilege token (one repo; issues+contents+PR; no admin). Treat all
   issue/PR/comment text as **untrusted data, never instructions** (prompt-injection). Never
   interpolate raw text into a shell command. Command allowlist for harnesses; `.env`
   git-ignored; no secrets in prompts/logs. No blind merges.
6. **Approval parsing.** Owner/maintainer only (`author_association` ∈ OWNER/MEMBER/COLLABORATOR);
   latest human comment; ignore bots, markers, quoted/code text; case-insensitive
   `APPROVE`/`CHANGES:`; ambiguous "APPROVE but change X" → `CHANGES`.

---

## Implementation contract (decided — build to this)

**1. Gate I/O.**
```
Inputs:  repo · run_id · env config · GitHub token · STALE_MIN · STUCK_MIN · MAX_ATTEMPTS
Outputs: intended actions only in dry-run; GitHub mutations only in deterministic/dispatch modes;
         structured log runtime/logs/gate/<run_id>.jsonl; exit code
Modes:   dry-run (print only; optional --audit-all-open) | deterministic-only | dispatch-enabled
Scope:   production queries only the scope label (AI-GATE-TEST in 2A–2E, AI from 2F)
Exit:    0 ok (incl. lock-held-skip) · 2 auth/permission · 3 unexpected (logged, fail-safe)
```
**2. Marker format.** HTML-comment `max-agency-dispatch` block (machine state); labels = human state.

**3. Benchmark pass/fail (Phase 0).** Coder ≥ 4/5 tasks, **zero critical failures** (commits
secrets · deletes unrelated files · ignores constraints · cannot open PR · fabricates structure).
Orchestrator: triage ≥ 4/5 + well-formed task issues. Named fallback per role.

**4. CTO verdict tokens (first line only).**
```
APPROVE_MERGE   (+ HUMAN-REVIEW: YES|NO)   REQUEST_CHANGES   ESCALATE_HUMAN   REJECT_CLOSE
```
Routes: APPROVE_MERGE+NO+CI-green → squash-merge; +YES → human; REQUEST_CHANGES → bounce to
task; ESCALATE_HUMAN → escalate; REJECT_CLOSE → close PR+issue. No token → not parsed.

**5. Issue-linking.** Every generated issue carries `Parent:`/`Plan:` refs; `PLAN.md` at
`/plans/issue-<N>/PLAN.md`. Chain: idea → plan approval → kickoff → child tasks, all traceable.

**6. PR ↔ issue convention.** Branch `max-agency/issue-<N>/attempt-<k>`; PR title `[AI-<N>]`;
body `Closes #<N>`. Drives stuck-detection and merged-close.

**7. Migration scope label.** New gate uses `AI-GATE-TEST` in 2A–2E; cut over to `AI` in 2F when
old pollers are disabled (also: old pollers ignore `AI-GATE-TEST`).

---

## Phased plan (boring, sequential, reversible)

- **Phase 0 — Doc-truth + model benchmark.** ✅ **DONE.** Coder benchmark done:
  `xiaomi/mimo-v2.5` scored 5/5 on `Wagner-Maximiliano/MDP-Massive-Development-Plan`
  (issues #4-#8, PRs #9-#13), zero critical failures, **promoted** — now
  `model.default` in `hermes-config/profiles/coder/config.yaml` and the live
  `~/.hermes/profiles/coder/config.yaml` (was `minimax/minimax-m3`, the interim
  patch from `b36d723`; that stays the named fallback). `codex` CLI installed and
  authenticated on the real host (ChatGPT-account login, `codex-cli 0.139.0`).
  Model availability verified live on that host: `gpt-5.4-mini` works, `gpt-5-mini`
  is rejected (HTTP 400 "not supported when using Codex with a ChatGPT account").
  **Orchestrator (triage) benchmark also done:** `gpt-5.4-mini` scored **5/5** on the
  same repo (triage issues #14-#18), zero critical failures, **promoted** (fallback
  `nvidia/nemotron-3-super-120b-a12b:free`). Cheapest accepted Codex variant
  (`gpt-5-mini` is rejected HTTP 400), `-c model_reasoning_effort=low`. Two harness
  fixes landed live: a Windows `.cmd`-shim exec resolver (`node ...\codex.js`, avoids
  `cmd.exe`/injection) and a **neutral working directory** for the orchestrator so
  codex (under `danger-full-access`) can't read the benchmark answer key or repo files
  — also mirrors production triage (issue + `gh` only). Both models meet the Phase 0
  bar → **Phase 0 closed.** (Duplicate flow-diagram HTML cleanup —
  `max-agency-flow-diagram.html` vs `max-agency-flow-diagram(Production).html` —
  intentionally deferred; cosmetic, not a gate dependency.)
- **Phase 1 — Cut MDP entirely.** ✅ **DONE.** Deleted 12 `skills/mdp-*` dirs + `docs/MDP.md`;
  stripped MDP refs from `agents/*.md`, `docs/AMA.md`, `skills/cto-review/SKILL.md`,
  `Highlevel_Plan_V2.0.md`, `README.md`, `Human_Runbook.md`, and the hermes profile
  configs/skills.txt; folded the file-safety + verification/rollback rules into
  `CODING_STANDARDS.md` §13; kept the role-functional skills. 47 unit tests still pass.
- **Phase 2 — Gate beside the old system, in small cuts** (old pollers run until 2F):
  - **2A** dry-run gate (no power). ✅ **DONE — built, unit tests, validated live.**
  - **2B** deterministic moves only (promotion, merged-close, approval routing) + idempotency
    markers; no LLM. ✅ **DONE — built, 47 unit tests total, validated live (promote +
    create-kickoff + idempotency on real issues).**
  - **2C** triage LLM only (+ hard subprocess timeout, mandatory from here on). ✅ **DONE —
    built, 93 unit tests, validated live.** `dispatch-enabled` mode invokes the orchestrator
    (`gpt-5.4-mini` via `codex`, **read-only** classify, issue text on stdin not argv) for
    scope-only issues; it returns a first-line verdict token and the **gate** applies the
    label deterministically (coder→`role:coder`+`ready`, architect→`role:architect`,
    needs-human→`needs-human`) + a rationale comment. Hard `--llm-timeout` (default 120 s) on
    every LLM/CLI call; hung/failed/unparsed triage = logged no-op, retried next tick. Triage
    is atomic (no label ⇒ no comment) and idempotent. **Setup dependency surfaced:** the repo
    must have the full workflow label set (Phase 3 `setup.ps1` creates them; a missing label
    fails safely).
  - **2D** coder harness (markers + recovery). ✅ **DONE — built, 103 unit tests, validated
    live.** `dispatch-enabled` dispatches the coder (`xiaomi/mimo-v2.5` via `wsl.exe →
    hermes`) for one `role:coder`+`ready` issue per tick: claim (`ready → in-progress` +
    in-flight `started`/attempt marker) **before** the blocking run, PR↔issue convention
    (branch `max-agency/issue-<N>/attempt-<k>`, title `[AI-<N>]`, body `Closes #<N>`), and
    time+PR-based recovery (stale marker, no PR → re-dispatch, attempt++ → `--max-attempts`
    → `needs-human`). Hard `--coder-timeout` on every run. **Safety fix surfaced live:** the
    coder MUST run from a **neutral cwd**, never the gate's repo — a `wsl.exe` child inherits
    the launcher's cwd and ran `git checkout` *inside our checkout* once (clobbering an
    uncommitted working tree); same neutral-cwd safeguard the Phase 0 orchestrator got.
  - **2E** architect/CTO harnesses + plan approval. ✅ **DONE — built, 129 unit tests,
    validated live.** Architect (Claude Opus, `claude -p --tools ""`) generates a PLAN from
    the brief → `plans/issue-<N>/PLAN.md` + approval comment + `role:architect → plan-ready`
    (CHANGES feeds feedback back); approve→kickoff is the 2B path. An open coder PR routes
    `in-progress → role:cto` (deterministic); the CTO reviews the diff and returns a
    first-line verdict that the gate routes: APPROVE_MERGE+`HUMAN-REVIEW:NO`+CI-green
    +`--auto-merge` → squash-merge (else hold `needs-human`); REQUEST_CHANGES → close PR +
    bounce to coder; ESCALATE_HUMAN → `needs-human`; REJECT_CLOSE → close PR + issue. Both
    harnesses: pure text-gen, no tools, hard `--claude-timeout`, neutral cwd, fail-safe.
    **Two robustness fixes surfaced live:** (a) in-place marker edits use the GraphQL
    `updateIssueComment` (node id) — REST PATCH 404s on the node id `gh` returns, which had
    let a failed marker write risk a *duplicate kickoff*; (b) `edit_labels` does adds-first
    then removes in separate calls, so a missing repo label can't half-strip an issue.
  - **Kickoff expansion** (orchestrator) ✅ **DONE — built, 138 unit tests, validated live.**
    Closes a gap between 2E and 2F: the `would-expand-kickoff` action was in the state machine
    but never wired. The orchestrator (`gpt-5.4-mini` via `codex`, read-only, approved
    `PLAN.md` on stdin) returns a JSON array of 1–6 task specs; the gate creates one coder
    task issue each (no-dep → `ready`, dep → `backlog` + `Depends-on:` resolved to real
    numbers), writes an in-flight `expanding` marker before any create (idempotent), then
    marks the kickoff `expanded` and closes it. The full new-idea → merge chain now connects.
  - **2F** decommission old pollers; cut scope label to `AI`; move single scheduler to Windows.
    ✅ **DONE.** Disabled + removed the WSL hermes *tick* timers/services (kept
    `hermes-gateway.service` — the coder harness needs it) and unregistered the disabled
    Claude Code routine Windows task; deleted the legacy poller files from the repo
    (`claude-code-routine/`, the tick `.service`s, `orchestrator-mechanics.sh`,
    `poll-prompts/`, `cron-jobs.md`) and slimmed `deploy.sh` to sync only the coder profile;
    flipped the gate's default `--scope-label` to **`AI`**; registered the gate as the single
    Windows Scheduled Task (`scripts/register-gate-task.ps1` → `MaxAgencyGate`, 5-min, verified
    a clean no-op against the live repo). Two fail-safe bugs fixed live: neutral-cwd
    `TemporaryDirectory(ignore_cleanup_errors=True)` (wsl left the dir busy on Windows → an
    `unexpected` crash) and per-issue try/except in the main loop (one bad issue no longer
    aborts the tick). **Old code kept in git history (reversible).**
- **Phase 3 — One-command onboarding.** Collapse setup into one `setup.ps1` that **implements
  the `SETUP.md` checklist** (created/maintained incrementally from Phase 2C on — setup
  requirements are captured the moment each phase surfaces them, not reconstructed here).
  This includes **reconciling/replacing the stale `scripts/setup-project.ps1`**, which
  predates the gate (creates `assigned:*`/`phase:*`/`review`/`blocked` labels and omits the
  scope label, `plan-ready`, and `needs-human`). Humans open issues in the GitHub UI (optional
  template auto-applies `AI`); trim `Human_Runbook.md`.

---

## How it works in practice (the human's view)

Human only ever: **opens a GitHub issue + adds `AI`**, and **replies to issues** (approve/answer).

- **Adopt existing repo:** `setup.ps1` once → add `AI` to issues you want worked → gate triages →
  build → review → merge. Non-`AI` issues ignored.
- **New idea:** `setup.ps1` → open one issue (free text + `AI`) → triage → Architect (Qs + PLAN +
  approval issue) → comment `APPROVE`/`CHANGES:` → kickoff → build loop.
- **Post-launch feature/fix:** empty board = zero cost. Open one issue + `AI`; triage picks the
  coder lane (small/clear) or architect lane (fuzzy/multi-step).

---

## Target architecture

One host (Windows) runs the only scheduled job (the gate, with the run lock). Gate does
deterministic moves, then dispatches harnesses on demand via `claude` (native), `codex` (native),
and `wsl.exe → hermes` (mimo). Each LLM run gets a specific prompt + issue number, does its work,
exits. Death mid-run is safe: next tick reconciles from GitHub + markers. GitHub = durable record,
PRs, CI, human board. Cross-vendor review preserved (mimo/GPT build → Claude CTO reviews).

---

## Verification (dry-run first, per sub-phase)

- **Phase 0:** ✅ both models passed (coder + orchestrator 5/5, promoted); docs match runtime.
- **Phase 1:** `grep -ri mdp` returns only history; agents still plan/build/review end-to-end.
- **Phase 2A:** ✅ printed decisions correct on live repo; scoped query excludes non-scope issues;
  run lock prevents overlap; structured logs emitted; zero mutations.
- **2B:** deterministic transitions + approval parsing correct; markers written; only owner
  approvals accepted; quoted/bot text ignored.
- **2C–2E:** each LLM invoked only for its state; one invocation per issue; stuck-recovery
  reclaims/retries to cap then `needs-human`; kill mid-dispatch → next tick recovers.
- **2F:** with old pollers off, a full new-idea→merge cycle completes with no double-dispatch/orphan.
- **Phase 3:** clean machine → `setup.ps1` → open issue + `AI` → merged PR, no manual label fixing.
