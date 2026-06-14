# Max Agency Gate

The gate is the single deterministic entry point that replaces the old polling daemons.
See the roadmap (`Simplification & Reliability Roadmap v3`) for the full design. This
directory is being built **one phase at a time, beside the old system**.

## Status: Phase 2A — dry-run only (read-only, changes nothing)

The gate currently does exactly six things and no more:

1. Reads open issues with the scope label (default `AI-GATE-TEST`).
2. Classifies each via the state-machine table (`classifier.py`).
3. Prints the intended action per issue (unknown/conflicting → `unknown-state`, no action;
   one corrupt issue never halts the board).
4. Writes a structured log to `runtime/logs/gate/<run_id>.jsonl`.
5. Uses `runtime/gate.lock` so runs cannot overlap.
6. **Changes nothing** — no labels, comments, or PRs are mutated.

## Run it

```sh
# needs an authenticated `gh` CLI; reads PROJECT_REPO or --repo
python3 gate/gate.py --repo owner/repo
python3 gate/gate.py --repo owner/repo --audit-all-open   # also list ignored (non-scope) issues
```

Printed output, one line per scoped issue:

```
#<issue> · <labels> · <detected_state> · <intended_action> · <reason>
```

Prove these printed decisions against real repos before any later phase grants the gate
write power.

## Layout

- `classifier.py` — pure state-machine logic (no I/O), fully unit-tested.
- `gate.py` — runner: lock, `gh` reads, marker/approval parsing, classify, print, JSONL log.
- `tests/` — `pytest` suite (state table + worked examples + parsing + dry-run smoke test).

```sh
python3 -m pytest gate -q
```

## Not in Phase 2A (deferred on purpose)

Subprocess timeouts (added at 2C), `needs-human` auto-labelling for invalid combos, label
governance, and any write/dispatch behaviour. The scope label flips from `AI-GATE-TEST` to
`AI` only at Phase 2F, when the old pollers are retired.
