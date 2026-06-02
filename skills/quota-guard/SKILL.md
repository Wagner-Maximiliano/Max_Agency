---
name: quota-guard
when_to_use: Routing a task to a model, or detecting that a vendor's usage window is filling up or exhausted.
applies_to: [orchestrator]
description: Free-first routing across vendor windows. Soft threshold at 70%, pause at 100%, auto-resume on reset, no human alert for normal degradation.
version: 1.0.0
license: MIT
metadata:
  hermes:
    tags: [max-agency, quota, cost, budget, windows]
---

# Quota Guard — Rolling-Window Routing

The agency runs on subscription windows, not a dollar budget. Each vendor (Anthropic, OpenAI via OpenRouter, etc.) has a rolling ~5-hour usage window. This skill keeps you within them without stalling work or alerting the human for expected degradation.

This is a **policy** skill. There is no engine — track state manually in `State.md` under a `## Quota status` section until a meter exists.

## When to Use

- Before dispatching any task to a model.
- When you notice a vendor crossed 70% used (soft threshold).
- When a vendor exhausts (100%) — pause its routing immediately.
- Every Orchestrator main-loop tick (`agents/orchestrator.md`).

## Procedure

### 1. Check headroom

Estimate per-vendor headroom from recent activity. Maintain in `State.md`:

```
## Quota status (manual, refreshed each loop tick)
- Anthropic (Claude Opus): ~60% used, reset ~2026-06-02 19:30 UTC
- OpenRouter (gpt-5):     ~25% used, reset ~2026-06-02 18:00 UTC
- OpenRouter (gpt-5-codex): ~15% used, reset ~2026-06-02 18:00 UTC
```

If unsure, assume 70% (conservative).

### 2. Route by headroom (free-first policy)

| Headroom on target vendor | Routing |
|---|---|
| > 80% | Paid tier OK. Route as planned. |
| 70–80% | Soft threshold approaching. Reserve paid windows for CTO / Architect / hard debug. Route routine coder work to alternate vendor if it has more headroom. |
| < 70% (soft threshold crossed) | Only the highest-value tier (Architect, CTO) uses this vendor. All routine work routes to alternate vendors with headroom, or queues. |
| Exhausted | **Do not route to this vendor.** Mark `paused_until=<reset>`. Use alternates. Auto-resume at reset. |

### 3. When the soft threshold is crossed (70%)

1. Log in `State.md`:
   ```
   - 2026-06-02 14:30: Anthropic crossed 71%. Routing routine work to OpenRouter until ~19:45 reset.
   ```
2. Redirect new routine work to vendors with headroom.
3. **No human alert.** This is expected operation.

### 4. When a window exhausts (100%)

1. Pause that vendor's tier immediately. Do not let in-flight retries hammer a 429.
2. Mark in `State.md`:
   ```
   - 2026-06-02 17:30: Anthropic exhausted. Paused. Reset ~19:45.
   ```
3. Reroute new work to remaining vendors. Builders already in-flight on the exhausted vendor pause and resume on reset — do not fail them.
4. **No human alert** unless *all paid vendors* exhaust simultaneously and only free tiers remain — then escalate per `docs/AMA.md §6`.

### 5. Auto-resume on reset

When `datetime.now() >= reset_time`:
1. Unpause the vendor in `State.md`.
2. Route new work to it again.
3. Resume any tasks that were paused mid-flight (their branches and worktrees are intact).
4. Log it:
   ```
   - 2026-06-02 19:45: Anthropic window reset. Resumed.
   ```

### 6. Cross-vendor balance

The point of separate vendor keys is that you always have a backup:

- CTO reviews and Architect planning can fall back to whichever frontier vendor has headroom — quality first.
- Coder work can absorb almost anywhere; route to the deepest headroom.
- Never let one vendor exhaust while another sits at 20%. Balance proactively.

## Pitfalls

- **Burning paid windows on cheap work.** If routine coder tasks keep hitting an Opus window, your routing is wrong. Push them to gpt-5-codex via OpenRouter instead.
- **Hammering an exhausted vendor.** A vendor at 100% returning 429s burns context. Pause immediately on detection.
- **Forgetting to log the soft-threshold crossing.** Next loop tick won't know to route conservatively. Always update `State.md` on the crossing.
- **Treating estimates as exact.** Token counting is approximate. Leave a 5–10% safety margin — treat 65% as if it's 70%.
- **Stalling on a reset.** If alternate vendors have headroom, route there. Don't wait.
- **Alerting the human on normal degradation.** Soft thresholds, single-vendor exhaustion, automatic resets — all silent. Only escalate when *all* paid vendors are simultaneously exhausted.

## Verification

- `State.md` `## Quota status` section is updated this loop tick.
- No `assigned:*` dispatch has gone to a vendor marked `paused_until` in the last minute.
- Routine coder work is not consuming the highest-tier vendor's window when alternates have headroom.
- Soft-threshold crossings and exhaustions are logged with timestamps.
- No human alert has fired for expected degradation; one has fired only if *all* paid vendors are exhausted.
