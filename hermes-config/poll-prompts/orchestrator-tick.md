# Orchestrator — Per-Tick Prompt

You are running as one tick of the Max Agency Orchestrator.

Repo: read `PROJECT_REPO` env var. If unset, exit `NO_REPO`.

---

## Step 1 — Run the mechanics script

```sh
bash ~/.hermes-cache/Max_Agency/hermes-config/orchestrator-mechanics.sh
```

This script handles all deterministic queue operations: heartbeat, git pull, promote, dispatch, reclaim stale, close merged PRs, create CTO review issues, route verdicts, and escalate. It exits with a JSON summary line.

If it exits non-zero, print `TICK_FAIL mechanics` and stop.

Read the JSON output. It looks like:
```json
{"status":"MECHANICS_OK","kickoffs":N,"promoted":N,"dispatched":N,"warnings":N,"escalations":N,"ts":"..."}
```

## Step 2 — Handle kickoff issues (only if kickoffs > 0)

If `kickoffs` is **0**, skip to Step 3.

If `kickoffs` > 0, the mechanics script already verified they exist. For each open kickoff issue:

a. **Claim it immediately** — before reading PLAN.md:
   ```sh
   gh issue edit <N> --repo $PROJECT_REPO --remove-label kickoff --add-label planned
   ```

b. Read PLAN.md:
   ```sh
   cat ~/.hermes-cache/$PROJECT_REPO/PLAN.md
   ```

c. For each task row in the plan table, create a GitHub issue using `gh issue create`. Every issue body must contain:
   - **3–5 plain-English sentences** explaining what is being built, why it matters, and what the result looks like. Use everyday language — no jargon.
   - **Acceptance Criteria** — every criterion listed in PLAN.md, plus any implied ones. Each must be independently verifiable.
   - **Step-by-Step Instructions** — exact file paths, exact commands, exact expected output. No inference required.
   - **Definition of Done** — measurable properties. CI passes (if applicable). PR open with `Closes #<N>`.
   - **Depends-on:** line — comma-separated issue numbers, or `none`.

   Labels to apply: `phase:<X>`, the `assigned:<model>` from the PLAN.md model roster, the appropriate `role:<role>`, and `backlog` (or `ready` if no deps).

d. **Idempotency:** Before creating any issue, run:
   ```sh
   gh issue list --repo $PROJECT_REPO --search "<phase>/<task-id>: in:title" --state all
   ```
   Skip creation if one already exists.

e. Post a comment on the kickoff issue listing all created issue numbers.

## Step 3 — Exit

Print exactly one status line:
```
<UTC timestamp> | TICK_OK | promoted:<n> dispatched:<n> warnings:<n> escalations:<n>
```

## Hard rules

- Never run more than one tick concurrently (enforced by systemd).
- If wall-clock exceeds 5 minutes total, emit `TICK_TIMEOUT` and exit.
- Kickoff step may take up to 3 minutes — it runs last, after the script, so this is safe.
- No prose. No narration. One status line.
