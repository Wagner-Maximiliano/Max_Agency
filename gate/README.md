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
- `tests/` — `pytest` suite (state table, worked examples, parsing, planner/writer, smoke tests).

```sh
python3 -m pytest gate -q
```

## Not in Phase 2A (deferred on purpose)

Subprocess timeouts (added at 2C), `needs-human` auto-labelling for invalid combos, label
governance, and any write/dispatch behaviour. The scope label flips from `AI-GATE-TEST` to
`AI` only at Phase 2F, when the old pollers are retired.
