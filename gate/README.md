# Max Agency Gate

The gate is the single deterministic entry point that replaces the old polling daemons.
See the roadmap (`Simplification & Reliability Roadmap v3`) for the full design. This
directory is being built **one phase at a time, beside the old system**.

## Status: Phase 2A ✅ + Phase 2B ✅

**2A — dry-run (read-only):** reads scoped issues, classifies via the state-machine table,
prints the intended action (unknown/conflicting → `unknown-state`, no action; one corrupt
issue never halts the board), logs to `runtime/logs/gate/<run_id>.jsonl`, uses
`runtime/gate.lock` to prevent overlap, **changes nothing**.

**2B — deterministic-only:** additionally executes the **non-LLM** moves —
`backlog → ready` promotion, closing issues whose linked PR merged, and approval routing
(`plan-ready` + owner `APPROVE` → create a linked kickoff issue; `+ CHANGES:` → back to
`role:architect`). Idempotency via a single per-issue marker comment. **No LLM is ever
called.** Every LLM action (triage / dispatch / architect / cto / recover) is deferred.

## Run it

```sh
# needs an authenticated `gh` CLI; reads PROJECT_REPO or --repo
python3 gate/gate.py --repo owner/repo                          # dry-run (default)
python3 gate/gate.py --repo owner/repo --audit-all-open         # also list ignored issues
python3 gate/gate.py --repo owner/repo --mode deterministic-only  # execute non-LLM moves
```

Printed output, one line per scoped issue:

```
#<issue> · <labels> · <detected_state> · <intended_action> · <reason>
```

Prove these printed decisions against real repos before any later phase grants the gate
write power.

## Layout

- `classifier.py` — pure state-machine logic (no I/O), fully unit-tested.
- `executor.py` — pure mutation **planner** (Decision → ops) + thin `gh` **writer** (2B).
- `gate.py` — runner: lock, `gh` reads, marker/approval parsing, classify, execute, JSONL log.
- `bench/` — Phase 0 model benchmark harness (see below).
- `tests/` — `pytest` suite (state table, worked examples, parsing, planner/writer, smoke tests).

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

Orchestrator benchmark not yet run. `codex` CLI (`codex-cli 0.139.0`) installed and
authenticated on the real host (ChatGPT-account login). Model availability verified
live on that host: `gpt-5.4-mini` works, while `gpt-5-mini` is **rejected** with
HTTP 400 ("not supported when using Codex with a ChatGPT account"). The orchestrator
candidate is therefore `gpt-5.4-mini` (cheapest accepted variant) with
`-c model_reasoning_effort=low` (triage is simple classification; low effort reduces
usage-quota consumption). `build_orchestrator_command` verified against the real CLI
(`-s danger-full-access` for `gh` label/comment writes, `--skip-git-repo-check`).

> **Environment note:** codex auth and model availability are host-specific, so the
> orchestrator benchmark must be run on the real host where the gate will run, not in
> a sandboxed dev environment. The benchmark issues (`[BENCH-TRIAGE-1..5]`, issues
> #14–#18 on `Wagner-Maximiliano/MDP-Massive-Development-Plan`) are created and ready;
> the live triage run is pending execution on the host.

## Not in Phase 2A (deferred on purpose)

Subprocess timeouts (added at 2C), `needs-human` auto-labelling for invalid combos, label
governance, and any write/dispatch behaviour. The scope label flips from `AI-GATE-TEST` to
`AI` only at Phase 2F, when the old pollers are retired.
