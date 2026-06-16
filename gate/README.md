# Max Agency Gate

The gate is the single deterministic entry point that replaces the old polling daemons.
See the roadmap (`Simplification & Reliability Roadmap v3`) for the full design. This
directory is being built **one phase at a time, beside the old system**.

## Status: Phase 0 ✅ + Phase 2A ✅ + Phase 2B ✅ + Phase 2C ✅

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
python3 gate/gate.py --repo owner/repo --mode dispatch-enabled    # + orchestrator triage (needs codex)
```

Printed output, one line per scoped issue:

```
#<issue> · <labels> · <detected_state> · <intended_action> · <reason>
```

Prove these printed decisions against real repos before any later phase grants the gate
write power.

## Layout

- `classifier.py` — pure state-machine logic (no I/O), fully unit-tested.
- `executor.py` — pure mutation **planner** (Decision → ops, incl. triage verdict → labels)
  + thin `gh` **writer** (2B/2C).
- `harness.py` — orchestrator triage: pure prompt/command/verdict-parse + a thin LLM runner
  with the **mandatory hard subprocess timeout** (2C).
- `gate.py` — runner: lock, `gh` reads, marker/approval parsing, classify, execute, JSONL log.
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
