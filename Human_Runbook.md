# Human Runbook — Max Agency

The only document you need to read.

## What this is

The Max Agency is an autonomous multi-agent development team coordinated through GitHub. Hermes hosts the non-Anthropic roles as two isolated profiles (`orchestrator`, `coder`); the Claude Code Windows app hosts the Anthropic roles (Architect, CTO, Anthropic Coder) on a Windows Task Scheduler routine. GitHub issues and labels are the bus.

You operate this system by **pasting prompts into Hermes**. All heavy lifting is done by Hermes — you almost never edit files directly.

## Once-only setup

### Step 1 — Push the baseline to the public repo

This local directory **is** the Max_Agency repo. Commit and push whatever is currently here:

```powershell
cd "C:\Users\lobster\Github_Projects\Max_Agency"
git add .
git commit -m "baseline: max agency scaffold"
git push
```

The public URL is: **https://github.com/Wagner-Maximiliano/Max_Agency** — this is what Hermes will `git clone` during bootstrap.

### Step 2 — Set environment variables for the current shell

```powershell
$env:AGENCY_REPO        = "Wagner-Maximiliano/Max_Agency"   # or the target project repo
$env:MAX_AGENCY_CACHE   = "$env:USERPROFILE\.hermes-cache\Max_Agency"
$env:TELEGRAM_BOT_TOKEN = "..."   # optional
$env:TELEGRAM_CHAT_ID   = "..."   # optional
```

Add the persistent ones to your PowerShell profile if you want them across sessions.

### Step 3 — Bootstrap Hermes (paste prompts H1 → H2 → H3 below)

Open a Hermes session in the **default** profile:

```
hermes chat
```

Paste **H1** first. Wait for it to finish. Verify the output. Then paste **H2**. Verify. Then paste **H3**.

### Step 4 — Install the Claude Code routine

```powershell
cd "C:\Users\lobster\Github_Projects\Max_Agency\claude-code-routine"
.\register-task.ps1 -Repo $env:AGENCY_REPO -ProjectPath "C:\Users\lobster\Github_Projects\Max_Agency" -IntervalMinutes 10
```

Verify with:

```powershell
Get-ScheduledTask -TaskName "MaxAgency-ClaudeCodeRoutine"
```

That's it. Setup is done.

---

## Per-project flow

For every new project after the agency is set up:

1. Create a new GitHub repo (in your account or org). Adjust `AGENCY_REPO` env var to point at it.
2. Open the Claude Code Windows app. Start a new session in any directory. Paste the **Architect kickoff prompt** (cheat sheet below) along with your project brief.
3. The Architect produces `PLAN.md`, hands it to the CTO (via a comment on a tracking issue), the CTO either approves or asks for changes, then you approve `PLAN.md` with one explicit ack.
4. From that point on, do not touch anything. Both Hermes profiles and the Claude Code routine pick up assigned issues automatically.
5. You only act again at: merge approval clicks, escalations on Telegram, end-of-project review.

---

## Hermes bootstrap prompts

Paste each block verbatim into a Hermes session (default profile, `hermes chat`). Do not edit them. Wait for the expected output before pasting the next one.

### H1 — Bootstrap profiles

```
You are bootstrapping the Max Agency on this machine. Follow these steps in order. Do NOT improvise. Do NOT skip steps. Print [OK] or [FAIL: <reason>] after each numbered step.

CONSTANTS:
- PUBLIC_REPO = https://github.com/Wagner-Maximiliano/Max_Agency
- CACHE_DIR   = $HOME/.hermes-cache/Max_Agency  (Windows: $env:USERPROFILE\.hermes-cache\Max_Agency)
- PROFILES    = orchestrator, coder

PROCEDURE:

1. If CACHE_DIR exists, run `git -C $CACHE_DIR pull --rebase`. Otherwise run `git clone $PUBLIC_REPO $CACHE_DIR`.

2. For each PROFILE in PROFILES:
   a. Run `hermes profile create <PROFILE>` (skip with [OK skipped: exists] if it already exists).
   b. Copy `$CACHE_DIR/hermes-config/profiles/<PROFILE>/config.yaml` to `$HOME/.hermes/profiles/<PROFILE>/config.yaml`.
   c. Copy `$CACHE_DIR/hermes-config/profiles/<PROFILE>/SOUL.md` to `$HOME/.hermes/profiles/<PROFILE>/SOUL.md`.
   d. Ensure dir `$HOME/.hermes/profiles/<PROFILE>/skills/` exists. Read `$CACHE_DIR/hermes-config/profiles/<PROFILE>/skills.txt` line by line; for each line that is not blank and does not start with `#`, copy `$CACHE_DIR/skills/<line>` into the profile's skills dir. Report the number copied.

3. Run `hermes profile list`. Confirm both `orchestrator` and `coder` appear.

OUTPUT CONTRACT:
- One [OK] or [FAIL: …] line per numbered step.
- Final line MUST be exactly: BOOTSTRAP_H1_COMPLETE
- If any step fails, stop immediately and emit BOOTSTRAP_H1_ABORT instead.

STOP. Do not proceed beyond step 3.
```

**Expected last line:** `BOOTSTRAP_H1_COMPLETE`

### H2 — Register cron jobs

```
You are continuing Max Agency bootstrap. H1 must have completed. Follow these steps. Print [OK] or [FAIL: <reason>] after each.

CONSTANTS:
- AGENCY_REPO   = (read from env var AGENCY_REPO; if unset, FAIL the whole prompt)
- CACHE_DIR     = $HOME/.hermes-cache/Max_Agency
- ORCH_PROMPT   = $CACHE_DIR/hermes-config/poll-prompts/orchestrator-tick.md
- CODER_PROMPT  = $CACHE_DIR/hermes-config/poll-prompts/coder-tick.md

PROCEDURE:

1. Verify AGENCY_REPO is set. If not, emit FAIL and abort.

2. Verify both prompt files exist. If either is missing, emit FAIL and abort.

3. Register the orchestrator cron job. Use this exact command (substitute $vars):
   hermes -p orchestrator cron add \
     --name "max-agency-orchestrator-tick" \
     --schedule "* * * * *" \
     --prompt-file "$ORCH_PROMPT" \
     --env "AGENCY_REPO=$AGENCY_REPO" \
     --env "MAX_AGENCY_CACHE=$CACHE_DIR" \
     --env "TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN:-}" \
     --env "TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID:-}" \
     --timeout 300
   If `hermes cron add` does not support --prompt-file in this version, read the file contents and pass them via --prompt instead.

4. Register the coder cron job:
   hermes -p coder cron add \
     --name "max-agency-coder-tick" \
     --schedule "* * * * *" \
     --prompt-file "$CODER_PROMPT" \
     --env "AGENCY_REPO=$AGENCY_REPO" \
     --env "MAX_AGENCY_CACHE=$CACHE_DIR" \
     --timeout 1500
   Same --prompt fallback if needed.

5. Run `hermes -p orchestrator cron list` and `hermes -p coder cron list`. Confirm each profile shows exactly one job named as above.

OUTPUT CONTRACT:
- One [OK] / [FAIL: …] line per step.
- Final line MUST be: BOOTSTRAP_H2_COMPLETE
- On any failure, emit BOOTSTRAP_H2_ABORT and stop.

STOP after step 5.
```

**Expected last line:** `BOOTSTRAP_H2_COMPLETE`

### H3 — Smoke test

```
You are continuing Max Agency bootstrap. H1 and H2 must have completed. Run all checks below. Print PASS or FAIL for each.

CHECKS:

1. `hermes profile list` includes both orchestrator and coder. (PASS/FAIL)
2. `hermes -p orchestrator cron list` shows max-agency-orchestrator-tick. (PASS/FAIL)
3. `hermes -p coder cron list` shows max-agency-coder-tick. (PASS/FAIL)
4. `cat $HOME/.hermes/profiles/orchestrator/SOUL.md` starts with "# Orchestrator — Soul". (PASS/FAIL)
5. `cat $HOME/.hermes/profiles/coder/SOUL.md` starts with "# Coder (Hermes side) — Soul". (PASS/FAIL)
6. `ls $HOME/.hermes/profiles/orchestrator/skills/ | wc -l` is at least 1. (PASS/FAIL)
7. `ls $HOME/.hermes/profiles/coder/skills/ | wc -l` is at least 1. (PASS/FAIL)
8. `env | grep AGENCY_REPO` returns a non-empty value. (PASS/FAIL)

OUTPUT CONTRACT:
- 8 lines, one per check: "CHECK <n>: PASS" or "CHECK <n>: FAIL — <reason>".
- Final line MUST be exactly: BOOTSTRAP_COMPLETE (if all PASS) or BOOTSTRAP_INCOMPLETE (otherwise).

STOP.
```

**Expected last line:** `BOOTSTRAP_COMPLETE`

---

## Per-project kickoff prompt (Architect, Claude Code app)

Open Claude Code in any directory. Paste this:

```
You are the Architect of the Max Agency. Your role contract is at https://github.com/Wagner-Maximiliano/Max_Agency/blob/main/agents/architect.md — fetch it (or clone the repo) and follow it exactly. Also read docs/MDP.md, docs/AMA.md, CODING_STANDARDS.md, and Highlevel_Plan_V2.0.md from the same repo.

Project brief:
<one paragraph stating goal, constraints, deadline if any>

Target repo: <owner/repo>  (must already exist on GitHub)

Begin your workflow. Ask up to 5 clarifying questions in one batched message, then produce PLAN.md and submit it for CTO review.
```

---

## Cheat sheet

| Prompt | When | Paste into |
|---|---|---|
| H1 | Once, first time setting up Hermes side | Hermes default profile |
| H2 | Once, immediately after H1 | Hermes default profile |
| H3 | Once, immediately after H2 | Hermes default profile |
| Architect kickoff | Once per new project | Claude Code Windows app |

After H1–H3 + the Architect kickoff, you should not paste anything else for normal operation. The cron jobs and the Task Scheduler routine handle the rest.

---

## Troubleshooting

| Symptom | Action |
|---|---|
| `hermes profile create` says "exists" | Fine, H1 handles this as `[OK skipped]`. Move on. |
| H1 fails at step 2c (config copy) | Check `$HOME/.hermes/profiles/<name>/` exists. If not, profile creation failed silently — run `hermes profile create <name>` manually and re-run H1. |
| H2 `--prompt-file` rejected | Your Hermes version uses `--prompt` only. The prompt instructs Hermes to fall back — if it didn't, paste H2 again with explicit "use --prompt fallback for both jobs". |
| H3 CHECK 8 FAIL | You forgot Step 2. Export `AGENCY_REPO` and re-run H3. |
| Cron ticks not firing | `hermes -p orchestrator cron list` — confirm schedule. Check Hermes daemon is running. Inspect `~/.hermes/profiles/orchestrator/escalations.log`. |
| Claude Code routine not picking up issues | `Get-ScheduledTask MaxAgency-ClaudeCodeRoutine`. Check History tab. Make sure `claude` CLI is on PATH. |
| Issue picked up by both Hermes and Claude Code | Labels collided. Each issue should have exactly one `assigned:*` label. Fix the label, re-add `ready`. |
| OpenRouter rate-limit errors | Reduce cron frequency: `hermes -p <profile> cron remove …` then re-add with `--schedule "*/5 * * * *"`. |

---

## What you, the human, do

Setup once. Kick off each project with the Architect prompt once. Approve merges. Resolve escalations on Telegram. Kill anything that loops. That's the whole job.

Everything else is delegated. If you find yourself doing more than this, the prompts need tightening — file an issue on the public repo with what felt manual.
