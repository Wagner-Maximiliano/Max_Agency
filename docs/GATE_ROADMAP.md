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
- **Candidate** models (to be *benchmarked, not assumed* — see Phase 0): orchestrator =
  GPT-5-mini (Codex); coder = `xiaomi/mimo-v2.5` (OpenRouter); CTO + Architect = Claude Opus.
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

- **Phase 0 — Doc-truth + model benchmark.** 🟡 **PARTIAL.** Coder benchmark done:
  `xiaomi/mimo-v2.5` scored 5/5 on `Wagner-Maximiliano/MDP-Massive-Development-Plan`
  (issues #4-#8, PRs #9-#13), zero critical failures, **promoted** — now
  `model.default` in `hermes-config/profiles/coder/config.yaml` and the live
  `~/.hermes/profiles/coder/config.yaml` (was `minimax/minimax-m3`, the interim
  patch from `b36d723`; that stays the named fallback). `codex` CLI now installed
  and authenticated (ChatGPT-account login, only `gpt-5.5` accepted — `gpt-5-mini`
  and other `gpt-5*` variants rejected). Orchestrator candidate updated to
  `gpt-5.5` (low reasoning effort); `build_orchestrator_command` verified.
  Remaining: run the live orchestrator (triage) benchmark; delete one duplicate
  flow-diagram HTML
  (`max-agency-flow-diagram.html` vs `max-agency-flow-diagram(Production).html`).
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
  - **2C** triage LLM only (+ hard subprocess timeout, mandatory from here on).
  - **2D** coder harness (markers + recovery).
  - **2E** architect/CTO harnesses + plan approval.
  - **2F** decommission old pollers; cut scope label to `AI`; move single scheduler to Windows.
- **Phase 3 — One-command onboarding.** Collapse setup into one `setup.ps1`; humans open issues
  in the GitHub UI (optional template auto-applies `AI`); trim `Human_Runbook.md`.

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

- **Phase 0:** models pass benchmark before promotion; docs match runtime.
- **Phase 1:** `grep -ri mdp` returns only history; agents still plan/build/review end-to-end.
- **Phase 2A:** ✅ printed decisions correct on live repo; scoped query excludes non-scope issues;
  run lock prevents overlap; structured logs emitted; zero mutations.
- **2B:** deterministic transitions + approval parsing correct; markers written; only owner
  approvals accepted; quoted/bot text ignored.
- **2C–2E:** each LLM invoked only for its state; one invocation per issue; stuck-recovery
  reclaims/retries to cap then `needs-human`; kill mid-dispatch → next tick recovers.
- **2F:** with old pollers off, a full new-idea→merge cycle completes with no double-dispatch/orphan.
- **Phase 3:** clean machine → `setup.ps1` → open issue + `AI` → merged PR, no manual label fixing.
