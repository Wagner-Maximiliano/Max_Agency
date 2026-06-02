# Human Runbook — Max Agency

The only document you need to read.

---

## How this fits together (read this first)

There are **three** locations involved in running the agency. They are not the same thing. Mixing them up is the #1 source of confusion.

| # | What it is | Where it lives | Who edits it | When you touch it |
|---|---|---|---|---|
| 1 | **The agency repo** — the *engine* (agent prompts, skills, scripts, configs) | Your machine: `C:\Users\lobster\Github_Projects\Max_Agency`<br>GitHub mirror: `github.com/Wagner-Maximiliano/Max_Agency` | You (rarely) — only to upgrade the agency itself | Almost never |
| 2 | **Hermes's cache** — Hermes's private read-only copy of the agency, auto-pulled from GitHub | Inside WSL: `~/.hermes-cache/Max_Agency` | Hermes only — auto-clone, auto-pull every tick | Never |
| 3 | **A project repo** — where actual product work happens: `PLAN.md`, issues, branches, PRs, code | A new GitHub repo per project, e.g. `github.com/Wagner-Maximiliano/my-cool-app` | The agents | Once at kickoff (create the empty repo on GitHub); then only approve merges and resolve escalations |

### Two environments, one machine

**Hermes runs inside WSL** (Windows Subsystem for Linux) — a Linux environment embedded in your Windows machine. WSL and Windows are isolated: a variable you set in Windows PowerShell (`$env:SOMETHING = "..."`) is **invisible to Hermes**, and vice versa.

This matters because:
- **Step 2** (env vars) only applies to the **Windows side** (the Claude Code routine).
- **H2** (the Hermes bootstrap prompt) does not rely on Windows env vars — the project repo is typed directly into the prompt before you paste it.

### The two big rules

1. **The agency repo is the toolkit. A project repo is the workshop.** You never copy files between them. The agents read agency files out of Hermes's cache (#2) and act on the project repo (#3) via GitHub.
2. **A project repo can be empty and remote-only.** You do not need to clone it to your machine. The agents work against it through the GitHub API.

---

## What this is

The Max Agency is an autonomous multi-agent development team coordinated through GitHub. Hermes hosts the non-Anthropic roles as two isolated profiles (`orchestrator`, `coder`); the Claude Code Windows app hosts the Anthropic roles (Architect, CTO, Anthropic Coder) on a Windows Task Scheduler routine. GitHub issues and labels are the bus.

You operate this system by **pasting prompts into Hermes and Claude Code**. You almost never edit files directly.

The agency's binding documents — read by every agent on every cold start — are:

- `Highlevel_Plan_V2.0.md` — architecture and gates
- `CODING_STANDARDS.md` — code rules every coder follows
- `docs/MDP.md` — operating layer (planning, roles, decision gates)
- `docs/AMA.md` — agent-to-agent protocol (identity, handoff, cross-provider review, escalation)
- `skills/` — reusable patterns each role loads on demand per its `applies_to` and `when_to_use`

---

## First-time setup (do this once per machine)

This sets up the **agency** (locations #1 + #2 above). You only do this once. You do **not** repeat it per project.

### Step 1 — Publish the agency repo to GitHub

The agency must exist on GitHub at **https://github.com/Wagner-Maximiliano/Max_Agency** so Hermes can `git clone` it into its WSL cache. If you've already done this (the repo is on GitHub), skip to Step 2.

If you are on a fresh machine and the local copy is not yet a git repo, open Windows PowerShell and run:

```powershell
cd "C:\Users\lobster\Github_Projects\Max_Agency"
git init -b main
git remote add origin https://github.com/Wagner-Maximiliano/Max_Agency.git
git add .
git commit -m "initial: max agency baseline"
git push -u origin main
```

From this point on, **any change to the agency itself goes through a PR** — branch off `main`, push, open a PR, merge from GitHub. You can do this from your phone.

### Step 2 — Set Windows environment variables (for Claude Code routine only)

> **Important:** These variables only affect the **Windows side** of the machine (the Claude Code routine / Task Scheduler job). Hermes runs in WSL and does not see these — that's handled separately in the H2 prompt below.

Open Windows PowerShell (Start menu → search "Windows PowerShell" → open it). The folder it starts in doesn't matter.

**Part A — set for the current window** (needed for Step 4 below):

```powershell
$env:MAX_AGENCY_CACHE = "$env:USERPROFILE\.hermes-cache\Max_Agency"
```

**Part B — make permanent** so they survive closing and reopening PowerShell:

```powershell
notepad $PROFILE
```

Notepad opens (say yes if it asks to create the file). Paste these lines at the bottom, then save and close:

```powershell
$env:MAX_AGENCY_CACHE = "$env:USERPROFILE\.hermes-cache\Max_Agency"
# Uncomment and fill in if you use Telegram for escalation alerts:
# $env:TELEGRAM_BOT_TOKEN = "your-bot-token-here"
# $env:TELEGRAM_CHAT_ID   = "your-chat-id-here"
```

This file runs every time you open a new PowerShell window, so the variables are always there.

### Step 3 — Bootstrap Hermes (paste prompts H1 → H2 → H3 below)

Hermes lives in WSL. Open your WSL terminal (Start menu → search "WSL" or "Ubuntu" or whichever distro you use) and run:

```bash
hermes chat
```

Paste **H1** first. Wait for `BOOTSTRAP_H1_COMPLETE`. Then **edit H2** (fill in your project repo on the one marked line), paste it, wait for `BOOTSTRAP_H2_COMPLETE`. Then paste **H3**, wait for `BOOTSTRAP_COMPLETE`.

### Step 4 — Install the Claude Code routine (Windows side)

This registers a Windows Task Scheduler job that wakes Claude Code every 10 minutes to pick up issues labelled `assigned:claude-*`. Run this in Windows PowerShell:

```powershell
$env:PROJECT_REPO = "Wagner-Maximiliano/your-project-repo"   # fill in your current project
cd "C:\Users\lobster\Github_Projects\Max_Agency\claude-code-routine"
.\register-task.ps1 -Repo $env:PROJECT_REPO -ProjectPath "C:\Users\lobster\Github_Projects\Max_Agency" -IntervalMinutes 10
```

Verify with:

```powershell
Get-ScheduledTask -TaskName "MaxAgency-ClaudeCodeRoutine"
```

That's it. Agency setup is done. You won't redo this unless you reinstall Windows or switch machines.

---

## Starting a new project

This is what you do **every time** you want the agency to build something new. Three steps.

### 1. Create an empty GitHub repo for the project

Go to github.com → New repository. Pick a name (e.g. `my-cool-app`). **Leave it completely empty** — no README, no .gitignore, no licence. The Architect creates everything.

You do **not** need to clone it to your machine.

### 2. Re-run H2 and Step 4 with the new project repo

**Hermes side (WSL):** Edit the `PROJECT_REPO` line at the top of the H2 prompt (see below) to your new project repo, then paste H2 into a Hermes chat session. This updates the cron jobs to point at the new project.

**Claude Code routine (Windows):** In Windows PowerShell:

```powershell
$env:PROJECT_REPO = "Wagner-Maximiliano/my-cool-app"
cd "C:\Users\lobster\Github_Projects\Max_Agency\claude-code-routine"
.\register-task.ps1 -Repo $env:PROJECT_REPO -ProjectPath "C:\Users\lobster\Github_Projects\Max_Agency" -IntervalMinutes 10
```

### 3. Kick off the Architect

Open the Claude Code Windows app. Start a new session in any directory — the folder doesn't matter, the Architect operates on GitHub. Paste the **Architect kickoff prompt** (below), filling in your project brief and the target repo name.

The Architect will ask you up to 5 clarifying questions, draft `PLAN.md`, get CTO approval, then ask you for one explicit ack before handing off to the Orchestrator.

From that point on, do nothing. Hermes and Claude Code pick up assigned issues automatically.

You only act again at: merge approval clicks, Telegram escalations, end-of-project review.

---

## Hermes bootstrap prompts

Open a Hermes session in WSL (`hermes chat`). Paste each block verbatim. Wait for the expected output before pasting the next one.

### H1 — Bootstrap profiles

```
You are bootstrapping the Max Agency on this machine. Follow these steps in order. Do NOT improvise. Do NOT skip steps. Print [OK] or [FAIL: <reason>] after each numbered step.

CONSTANTS:
- PUBLIC_REPO = https://github.com/Wagner-Maximiliano/Max_Agency
- CACHE_DIR   = $HOME/.hermes-cache/Max_Agency
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

---

### H2 — Register cron jobs

> **Before pasting:** replace `Wagner-Maximiliano/REPLACE-WITH-YOUR-PROJECT-REPO` on the first line with your actual project repo (e.g. `Wagner-Maximiliano/Surviving_The_AI_World`). Everything else paste verbatim.

```
PROJECT_REPO = Wagner-Maximiliano/REPLACE-WITH-YOUR-PROJECT-REPO

You are continuing Max Agency bootstrap. H1 must have completed. Follow these steps. Print [OK] or [FAIL: <reason>] after each.

CONSTANTS (use the PROJECT_REPO value from the first line of this message):
- CACHE_DIR     = $HOME/.hermes-cache/Max_Agency
- ORCH_PROMPT   = $CACHE_DIR/hermes-config/poll-prompts/orchestrator-tick.md
- CODER_PROMPT  = $CACHE_DIR/hermes-config/poll-prompts/coder-tick.md

PROCEDURE:

1. Confirm PROJECT_REPO is set from the first line of this message. Print its value. If the value is still the placeholder "REPLACE-WITH-YOUR-PROJECT-REPO", emit FAIL and abort.

2. Verify both prompt files exist. If either is missing, emit FAIL and abort.

3. Register the orchestrator cron job:
   hermes -p orchestrator cron add \
     --name "max-agency-orchestrator-tick" \
     --schedule "* * * * *" \
     --prompt-file "$ORCH_PROMPT" \
     --env "PROJECT_REPO=$PROJECT_REPO" \
     --env "MAX_AGENCY_CACHE=$CACHE_DIR" \
     --env "TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN:-}" \
     --env "TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID:-}" \
     --timeout 300
   If `hermes cron add` does not support --prompt-file, read the file and pass contents via --prompt instead.

4. Register the coder cron job:
   hermes -p coder cron add \
     --name "max-agency-coder-tick" \
     --schedule "* * * * *" \
     --prompt-file "$CODER_PROMPT" \
     --env "PROJECT_REPO=$PROJECT_REPO" \
     --env "MAX_AGENCY_CACHE=$CACHE_DIR" \
     --timeout 1500
   Same --prompt fallback if needed.

5. Run `hermes -p orchestrator cron list` and `hermes -p coder cron list`. Confirm each shows exactly one job. Print the PROJECT_REPO value baked into each job's env to confirm it is correct.

OUTPUT CONTRACT:
- One [OK] / [FAIL: …] line per step.
- Final line MUST be: BOOTSTRAP_H2_COMPLETE
- On any failure, emit BOOTSTRAP_H2_ABORT and stop.

STOP after step 5.
```

**Expected last line:** `BOOTSTRAP_H2_COMPLETE`

---

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
8. The orchestrator cron job env contains a non-placeholder PROJECT_REPO value (not empty, not "REPLACE-WITH-YOUR-PROJECT-REPO"). Print the value. (PASS/FAIL)

OUTPUT CONTRACT:
- 8 lines, one per check: "CHECK <n>: PASS" or "CHECK <n>: FAIL — <reason>".
- Final line MUST be exactly: BOOTSTRAP_COMPLETE (if all PASS) or BOOTSTRAP_INCOMPLETE (otherwise).

STOP.
```

**Expected last line:** `BOOTSTRAP_COMPLETE`

---

## Architect kickoff prompt (Claude Code app)

Open Claude Code in any directory. Fill in the two placeholders and paste:

```
You are the Architect of the Max Agency. Your role contract is at https://github.com/Wagner-Maximiliano/Max_Agency/blob/main/agents/architect.md — fetch it (or clone the repo) and follow it exactly. Also read docs/MDP.md, docs/AMA.md, CODING_STANDARDS.md, and Highlevel_Plan_V2.0.md from the same repo.

Project brief:
<one paragraph stating goal, constraints, deadline if any>

Target repo: <owner/repo>   (the empty GitHub repo you just created — this is the PROJECT repo, not the agency)

Begin your workflow. Ask up to 5 clarifying questions in one batched message, then produce PLAN.md and submit it for CTO review.
```

---

## Cheat sheet

| Prompt | When | Where |
|---|---|---|
| H1 | Once, first-time agency setup | WSL — `hermes chat` |
| H2 | Once after H1; re-run when switching projects (edit the PROJECT_REPO line first) | WSL — `hermes chat` |
| H3 | Once, immediately after H2 | WSL — `hermes chat` |
| Architect kickoff | Once per new project | Claude Code Windows app |

---

## Troubleshooting

| Symptom | Action |
|---|---|
| `hermes profile create` says "exists" | Fine — H1 handles this as `[OK skipped]`. Move on. |
| H1 fails at step 2c (config copy) | Check `$HOME/.hermes/profiles/<name>/` exists in WSL. If not, run `hermes profile create <name>` manually in WSL and re-run H1. |
| H2 `--prompt-file` rejected | Your Hermes version uses `--prompt` only. The prompt instructs Hermes to fall back — if it didn't, paste H2 again with "use --prompt fallback for both jobs" added to the top. |
| H2 FAIL: placeholder not replaced | You forgot to edit the `PROJECT_REPO = Wagner-Maximiliano/REPLACE-...` line at the top of H2 before pasting. Edit it and re-paste. |
| H2 FAIL: prompt files missing | H1 didn't complete successfully — the cache wasn't cloned. Re-run H1 first. |
| H3 CHECK 8 FAIL | H2 didn't complete or baked in the placeholder. Re-edit the PROJECT_REPO line in H2 and re-run H2, then H3. |
| I set `$env:PROJECT_REPO` in PowerShell but Hermes can't see it | Expected — PowerShell and WSL are separate environments. For Hermes: edit the PROJECT_REPO line in H2 and re-paste it. For the Claude Code routine (Windows): set the PowerShell env var and re-run `register-task.ps1`. |
| Cron ticks not firing | In WSL: `hermes -p orchestrator cron list` — confirm schedule. Check Hermes daemon is running (`hermes status`). Inspect `~/.hermes/profiles/orchestrator/escalations.log`. |
| Cron ticks running against the wrong project | In WSL: re-edit the PROJECT_REPO line in H2 and re-paste it. This replaces the baked-in value. |
| Claude Code routine not picking up issues | In Windows PowerShell: `Get-ScheduledTask MaxAgency-ClaudeCodeRoutine`. Check History tab. Make sure `claude` CLI is on PATH. |
| Claude Code routine pointing at wrong project | Re-run `register-task.ps1` with the new `-Repo` value; it replaces the existing task. |
| Issue picked up by both Hermes and Claude Code | Labels collided. Each issue should have exactly one `assigned:*` label. Fix the label, re-add `ready`. |
| OpenRouter rate-limit errors | In WSL: `hermes -p <profile> cron remove max-agency-<profile>-tick` then re-add with `--schedule "*/5 * * * *"`. |
| "Where do I edit the agency?" | In `C:\Users\lobster\Github_Projects\Max_Agency` on Windows. Push via PR. Hermes pulls from GitHub on the next cron tick. |
| "Where do I edit the project's code?" | Nowhere — the agents do. You only review PRs. |

---

## What you, the human, do

- **Once per machine:** first-time agency setup (Steps 1–4 above). Maybe an hour.
- **Once per project:** create empty GitHub repo, edit the PROJECT_REPO line in H2 and re-paste it, re-run Step 4, paste Architect kickoff. Five minutes.
- **Ongoing:** approve merges. Resolve escalations on Telegram. Kill anything that loops.

Everything else is delegated. If you find yourself doing more than this, the prompts need tightening — file an issue on the agency repo with what felt manual.

---

## Phone workflow

Day-to-day from your phone, using the GitHub mobile app or `github.com` in a browser:

- **Approve merges** — open the PR, scan CTO's `VERDICT: APPROVED` comment + green CI, hit **Merge**.
- **Resolve escalations** — Telegram pings; reply on Telegram, or comment on the linked issue from GitHub.
- **Skim status** — the `State.md` file in the project repo root is the snapshot; the Orchestrator regenerates it every tick.
- **Pause everything** — add label `blocked` to any open issue from the GitHub mobile app. Orchestrator stops dispatching new work for that phase next tick.

You should never need to push code from the phone. If you do, the agents have lost the plot — file an issue describing what they got stuck on.
