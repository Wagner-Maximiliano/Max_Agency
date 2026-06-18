# Max Agency Gate

The gate is the single deterministic entry point that replaces the old polling daemons.
See the roadmap (`Simplification & Reliability Roadmap v3`) for the full design. This
directory is being built **one phase at a time, beside the old system**.

## Status: Phase 0 ✅ + 2A ✅ + 2B ✅ + 2C ✅ + 2D ✅ + 2E ✅ + 2F ✅ + soak-hardening ✅ (next: Phase 3 onboarding)

**Soak-test backlog (2026-06-18)** — three bugs + two features from the first live soak test,
all shipped (170 unit tests): **BUG-2** marker comments now carry a visible stub line (were
blank HTML-only comments); **BUG-1** an approved kickoff is expanded in the *same* tick it's
created (no idle wait); **BUG-3** `check_model coder --smoke` runs a real branch→commit→PR
round-trip and verifies the PR actually landed (a clean exit with no PR is the failure the
ping missed); **FEAT-1** full LLM transcript logging at the single `run_llm` chokepoint
(`runtime/logs/transcripts/<run_id>.txt`, zero extra tokens, secrets never logged); **FEAT-2**
a daily `MaxAgencyLogCleanup` task prunes logs past a retention window (default 7 days).

**2F — cutover:** the old polling system is **retired**. The WSL hermes tick timers and the
Claude Code routine are gone; the gate is the single scheduled job, registered as a Windows
Scheduled Task via `scripts/register-gate-task.ps1` (`MaxAgencyGate`). The production scope
label is now **`AI`** (default). The gate is safe to schedule: an empty `AI` board exits at
zero cost, and `AI` is the per-issue opt-in + kill-switch. `hermes-gateway.service` (the core
hermes daemon the coder harness needs) and `hermes-config/profiles/coder/` are kept.

**2A — dry-run (read-only):** reads scoped issues, classifies via the state-machine table,
prints the intended action (unknown/conflicting → `unknown-state`, no action; one corrupt
issue never halts the board), logs to `runtime/logs/gate/<run_id>.jsonl`, uses
`runtime/gate.lock` to prevent overlap, **changes nothing**.

**2B — deterministic-only:** additionally executes the **non-LLM** moves —
`backlog → ready` promotion, closing issues whose linked PR merged, and approval routing
(`plan-ready` + owner `APPROVE` → create a linked kickoff issue; `+ CHANGES:` → back to
`role:architect`). Idempotency via a single per-issue marker comment. **No LLM is ever
called.**

**2C — dispatch-enabled (first real LLM call):** additionally invokes the **orchestrator**
(`gpt-5.4-mini` via `codex`) to **triage** scope-only issues. The LLM only *classifies*
(read-only sandbox, no tools; the issue text is fed on **stdin**, never in argv), returning
a first-line verdict token (`ROLE_CODER`/`ROLE_ARCHITECT`/`NEEDS_HUMAN`) + a one-line reason.
The **gate** then applies the label itself via the deterministic executor (least privilege):
coder → `role:coder`+`ready` (coherent lane entry), architect → `role:architect`,
needs-human → `needs-human`, plus a rationale comment. Every LLM/CLI call runs under a
**hard subprocess timeout** (`--llm-timeout`, default 120 s); a hung/failed/unparsed triage
is a logged no-op, retried next tick — it never freezes the gate. Triage is atomic (no label
⇒ no comment) and idempotent (the applied label moves the issue out of scope-only). The other
LLM actions (dispatch-coder / architect / cto / recover) remain deferred to 2D–2E.

**2D — coder dispatch + recovery:** in `dispatch-enabled` mode the gate now also dispatches
the **coder** (`xiaomi/mimo-v2.5` via `wsl.exe → hermes`) for one `role:coder`+`ready` issue
per tick. It **claims** the issue first (move `ready → in-progress` + write the in-flight
`<!-- max-agency-dispatch … status: started attempt: k -->` marker) **before** the blocking
run, so a crash mid-build is recoverable. Only the integer issue number reaches the command —
hermes reads the untrusted issue text itself via `gh` (least exposure). The coder follows the
PR↔issue convention (branch `max-agency/issue-<N>/attempt-<k>`, PR title `[AI-<N>]`, body
`Closes #<N>`). **Recovery** is time + PR based: an `in-progress` issue whose marker has gone
stale (older than `--stuck-min`) with no open PR is re-dispatched (attempt incremented) up to
`--max-attempts`, then parked `needs-human`. Every coder run is under a hard `--coder-timeout`
(default 1800 s) and — critically — runs from a **neutral temp cwd**, never the gate's repo
(a `wsl.exe` child inherits the launcher's cwd and would otherwise run `git` under `--yolo`
inside our checkout). At most one coder is dispatched per tick (a build is long + synchronous).

**2E — architect + CTO (Claude Opus via the `claude` CLI):** the last two LLM lanes.
- **Architect** (`would-invoke-architect`): generates an implementation PLAN from the issue
  brief (pure text-gen, `claude -p --tools ""`, brief on stdin, neutral cwd), writes it to
  `plans/issue-<N>/PLAN.md`, posts it as an approval comment, and flips `role:architect →
  plan-ready`. A `CHANGES:` revision feeds the owner's feedback back to the architect.
  Approval routing (`APPROVE → kickoff` / `CHANGES → revise`) is the existing 2B path.
- **CTO** (`would-invoke-cto`): an open coder PR routes `in-progress → role:cto`
  (deterministic), then the CTO reviews the diff + issue/PR context and returns a first-line
  verdict token. The gate routes it: **APPROVE_MERGE** + `HUMAN-REVIEW: NO` + CI green +
  `--auto-merge` → squash-merge (closes the issue); otherwise hold `needs-human` (no blind
  merge). **REQUEST_CHANGES** → close the PR + bounce to the coder lane (attempt++).
  **ESCALATE_HUMAN** → `needs-human`. **REJECT_CLOSE** → close PR + issue.

Every architect/CTO call is pure text generation (no tools), under the hard `--claude-timeout`,
from a neutral cwd; a hung/failed/unparsed result is a logged no-op, retried next tick.

**Kickoff expansion (orchestrator):** closes the new-idea loop. A `kickoff` issue (created by
2B on `APPROVE`) is expanded by the orchestrator (`gpt-5.4-mini` via `codex`, read-only): the
gate feeds the approved `PLAN.md` on stdin, the model returns a strict JSON array of 1–6
task specs (`title`/`body`/`depends_on`), and the gate creates one coder task issue per task
(no deps → `role:coder`+`ready`; with deps → `backlog` + a `Depends-on: #…` line resolved to
the real numbers, promoted by 2B once the deps close). An in-flight `expanding` marker is
written **before** any create (a crash can't trigger a duplicate expand); on success the
kickoff is marked `expanded` and closed. This makes the full chain — idea → triage →
architect → plan → approve → kickoff → **expand** → coder → PR → CTO → merge — complete.

> **Setup dependency:** the gate's writes require the full workflow label set to **exist on
> the repo** (scope label + `role:*` + `backlog`/`ready`/`in-progress`/`plan-ready`/`kickoff`/
> `needs-human`). A missing label makes the atomic label-edit fail safely (logged, no comment,
> retried). The authoritative, maintained list is **`SETUP.md` §3** (the root setup-requirements
> checklist that Phase 3 `setup.ps1` will automate). The old `scripts/setup-project.ps1` does
> **not** create the correct set — see `SETUP.md`.

## Run it

```sh
# needs an authenticated `gh` CLI; reads PROJECT_REPO or --repo
python3 gate/gate.py --repo owner/repo                          # dry-run (default)
python3 gate/gate.py --repo owner/repo --audit-all-open         # also list ignored issues
python3 gate/gate.py --repo owner/repo --mode deterministic-only  # execute non-LLM moves
python3 gate/gate.py --repo owner/repo --mode dispatch-enabled    # + triage (codex) + coder (wsl->hermes)
```

`dispatch-enabled` runs the real LLM harnesses: orchestrator triage (needs `codex`) **and**
coder dispatch/recovery (needs `wsl.exe → hermes`). When dispatching coders, set
`--stale-min >= --coder-timeout/60` so the run lock isn't reclaimed during a long build.

Printed output, one line per scoped issue:

```
#<issue> · <labels> · <detected_state> · <intended_action> · <reason>
```

Prove these printed decisions against real repos before any later phase grants the gate
write power.

## Layout

- `classifier.py` — pure state-machine logic (no I/O), fully unit-tested.
- `executor.py` — pure mutation **planner** (Decision → ops, incl. triage verdict → labels
  and coder dispatch/recovery ops) + thin `gh` **writer** (2B/2C/2D).
- `harness.py` — LLM harnesses: pure prompt/command/verdict-parse for triage (2C), the coder
  command (2D), and the architect + CTO commands/parsers (2E) + a thin LLM runner with the
  **mandatory hard subprocess timeout** and a neutral-`cwd` option for tool-using harnesses.
  Also the **transcript writer** (FEAT-1): `run_llm`'s optional `transcript=` records the
  prompt + raw reply per call; the argv (with the coder's env-source prefix) is never logged.
- `check_model.py` — per-role model self-test (`python gate/check_model.py <role>`); a ping by
  default, or `coder --smoke --repo owner/repo` for the full agentic round-trip (FEAT-1 BUG-3).
- `gate.py` — runner: lock, `gh` reads, marker/approval parsing, classify, execute, JSONL log,
  + per-run LLM transcripts (`runtime/logs/transcripts/<run_id>.txt`).
- `bench/` — Phase 0 model benchmark harness (see below).
- `tests/` — `pytest` suite (state table, worked examples, parsing, planner/writer, triage,
  smoke tests).

```sh
python3 -m pytest gate -q
```

## Phase 0 — model benchmark harness (`bench/`)

Pure tasks/scorer + a thin runner CLI, evaluating the coder candidate
(`xiaomi/mimo-v2.5`, fallback `minimax/minimax-m3`) and the orchestrator candidate
(`gpt-5.4-mini`, fallback `nvidia/nemotron-3-super-120b-a12b:free`) against 5 tasks each.
Promotion rule: ≥4/5 pass **and** zero critical failures (secrets / deleted-unrelated /
ignored-constraints / no-PR / fabricated-structure), else fall back, else keep the live
model and escalate.

```sh
python gate/bench/runner.py list                                            # show tasks + candidates
python gate/bench/runner.py prep --repo OWNER/REPO --role coder             # dry-run issue creation
python gate/bench/runner.py dispatch --role coder --task-id coder-1 \
    --repo OWNER/REPO --issue N                                             # dry-run dispatch command
# add --live to actually create issues / run the harness (hard subprocess timeout, default 30 min)
```

Status: harness built and unit-tested (72 tests). **Coder benchmark complete:**
`xiaomi/mimo-v2.5` scored 5/5 on `Wagner-Maximiliano/MDP-Massive-Development-Plan`
(PRs #9-#13, issues #4-#8), zero critical failures — **promoted** and now the live
`model.default` in `hermes-config/profiles/coder/config.yaml` (and the matching
`~/.hermes/profiles/coder/config.yaml`), replacing the interim `minimax/minimax-m3`
patch from commit `b36d723`. `minimax/minimax-m3` remains the named fallback.

**Orchestrator benchmark complete:** `gpt-5.4-mini` scored **5/5** on
`Wagner-Maximiliano/MDP-Massive-Development-Plan` (triage issues #14–#18), zero
critical failures — **promoted**. It correctly classified `role:coder` (#14),
`role:architect` (#15, #17), `needs-human` (#16), and recognized the deliberately
bundled typo-fix-plus-CI-rewrite (#18) instead of silently mislabeling it. `codex`
CLI (`codex-cli 0.139.0`) is authenticated on the real host (ChatGPT-account login);
`gpt-5.4-mini` is the cheapest accepted variant (`gpt-5-mini` is rejected with
HTTP 400), run with `-c model_reasoning_effort=low`. Named fallback:
`nvidia/nemotron-3-super-120b-a12b:free`.

**Phase 0 is closed** — both models meet the bar. (The duplicate flow-diagram HTML
cleanup was intentionally deferred: cosmetic, not a gate dependency.)

Two harness fixes landed during the live run:
- **Windows exec shim:** `codex` on Windows is a `.cmd` npm shim that `subprocess`
  can't launch directly (`[WinError 2]`). `_runnable_argv` rewrites it to invoke the
  underlying `node ...\codex.js`, avoiding `cmd.exe` (so no shell-quoting/injection
  surface when issue text is later passed through — Phase 2C).
- **Neutral working directory:** the orchestrator (codex under `danger-full-access`)
  now runs from a throwaway temp dir, never the repo. Running it inside the repo let
  codex read the benchmark's own answer key (`tasks.py` rubric); the neutral cwd also
  mirrors production triage (issue + `gh` only).

## Not in Phase 2A (deferred on purpose)

Subprocess timeouts (added at 2C), `needs-human` auto-labelling for invalid combos, label
governance, and any write/dispatch behaviour. The scope label flips from `AI-GATE-TEST` to
`AI` only at Phase 2F, when the old pollers are retired.
