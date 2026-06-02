# Human Runbook — Max Agency

The only document you need to read.

---

## How this fits together (read this first)

There are **three** locations involved in running the agency. They are not the same thing. Mixing them up is the #1 source of confusion.

| # | What it is | Where it lives | Who edits it | When you touch it |
|---|---|---|---|---|
| 1 | **The agency repo** — the *engine* (agent prompts, skills, scripts, configs) | Your machine: `C:\Users\lobster\Github_Projects\Max_Agency`<br>GitHub mirror: `github.com/Wagner-Maximiliano/Max_Agency` | You (rarely) — only to upgrade the agency itself (add a skill, tweak an agent prompt) | Almost never |
| 2 | **Hermes's cache** — Hermes's private read-only copy of the agency, auto-pulled from GitHub | `C:\Users\lobster\.hermes-cache\Max_Agency` | Hermes only — auto-clone, auto-pull every tick | Never |
| 3 | **A project repo** — where actual product work happens for one project: `PLAN.md`, GitHub issues, branches, PRs, the product code | A new GitHub repo per project, e.g. `github.com/Wagner-Maximiliano/my-cool-app` | The agents | Once at kickoff (create empty repo, set env var); then only to approve merges and resolve escalations |

### The two big rules

1. **The agency repo is the toolkit. A project repo is the workshop.** You never copy files from the agency into a project. The agents read agency files out of Hermes's cache (#2) and act on the project repo (#3) via the GitHub API.
2. **A project repo can be empty and remote-only.** You do not have to clone it to your machine. The Architect, CTO, Orchestrator, and coders all talk to it through GitHub.

### The `PROJECT_REPO` env var

`PROJECT_REPO` (set in your shell) tells Hermes and the Claude Code routine **which project is currently active**. Change it when you start a new project. The agency itself never changes — only the project pointer changes.

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

This sets up the **agency** (location #1 + #2 above). You only do this once. You do **not** repeat it per project.

### Step 1 — Publish the agency repo to GitHub

The agency must exist on GitHub at **https://github.com/Wagner-Maximiliano/Max_Agency** so Hermes can `git clone` it into its cache. If you've followed the previous setup steps in this repo, this is already done — skip to Step 2.

If you are setting up on a fresh machine and the local copy is not yet a git repo:

```powershell
cd "C:\Users\lobster\Github_Projects\Max_Agency"
git init -b main
git remote add origin https://github.com/Wagner-Maximiliano/Max_Agency.git
git add .
git commit -m "initial: max agency baseline"
git push -u origin main
```

If you already have a clone and just want to sync local agency-side work:

```powershell
cd "C:\Users\lobster\Github_Projects\Max_Agency"
git add .
git commit -m "<one-line what changed>"
git push
```

From this point on, **any change to the agency itself goes through a PR** — branch off `main`, push, open a PR, merge from GitHub (you can do this from your phone via the GitHub mobile app or web).

### Step 2 — Set persistent environment variables

These tell Hermes where the agency lives. `PROJECT_REPO` you'll change later per project — for now leave it unset or pointed at the agency itself for smoke-testing.

```powershell
$env:MAX_AGENCY_CACHE   = "$env:USERPROFILE\.hermes-cache\Max_Agency"
$env:TELEGRAM_BOT_TOKEN = "..."   # optional, for escalations
$env:TELEGRAM_CHAT_ID   = "..."   # optional
# PROJECT_REPO is set per-project, not here. See "Starting a new project" below.
```

Add the persistent ones to your PowerShell profile if you want them across sessions:

```powershell
notepad $PROFILE
```

…then paste the same lines into the profile file and save.

### Step 3 — Bootstrap Hermes (paste prompts H1 → H2 → H3 below)

Open a Hermes session in the **default** profile:

```powershell
hermes chat
```

Paste **H1** first. Wait for it to finish. Verify it ends with `BOOTSTRAP_H1_COMPLETE`. Then paste **H2**. Verify `BOOTSTRAP_H2_COMPLETE`. Then paste **H3**. Verify `BOOTSTRAP_COMPLETE`.

> For H2 to succeed, `PROJECT_REPO` must be set in your shell. Set it to `Wagner-Maximiliano/Max_Agency` for the smoke test, or to your first real project repo if you already created it. You can change it later — H2 only reads it once to bake into the cron jobs' env.

### Step 4 — Install the Claude Code routine

This registers a Windows Task Scheduler job that wakes Claude Code every 10 minutes to pick up issues labelled `assigned:claude-*`.

```powershell
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

This is what you do **every time** you want the agency to build something new. It's three small steps.

### 1. Create an empty GitHub repo for the project

Go to github.com → New repository. Pick a name (e.g. `my-cool-app`). Leave it empty (no README, no .gitignore, no license — the Architect will create everything).

You do **not** need to clone it to your machine. The agents work against it remotely.

### 2. Point the agency at the new project

In your PowerShell, update the env var:

```powershell
$env:PROJECT_REPO = "Wagner-Maximiliano/my-cool-app"
```

If your cron jobs are already running with an old `PROJECT_REPO` baked in, re-register them by pasting **H2** again — it'll update the env on the existing jobs (or remove and re-add them).

You may also want to re-run Step 4 of first-time setup so the Claude Code routine targets the new repo:

```powershell
cd "C:\Users\lobster\Github_Projects\Max_Agency\claude-code-routine"
.\register-task.ps1 -Repo $env:PROJECT_REPO -ProjectPath "C:\Users\lobster\Github_Projects\Max_Agency" -IntervalMinutes 10
```

(`register-task.ps1` replaces the existing scheduled task if one is registered under the same name.)

### 3. Kick off the Architect

Open the Claude Code Windows app. Start a new session in any directory — directory doesn't matter, the Architect operates on the GitHub project repo, not on local files. Paste the **Architect kickoff prompt** (see below), filling in your project brief and the target repo.

The Architect will:

1. Clone the **agency repo** for reference (to read its own role contract + MDP/AMA/standards/skills).
2. Ask you up to 5 clarifying questions in one batch.
3. Draft `PLAN.md` and commit it to the **project repo**.
4. Open a tracking issue and request CTO review.
5. After CTO approves and you give one explicit ack, hand off to the Orchestrator.

From that point on you do not touch anything. Both Hermes profiles and the Claude Code routine pick up assigned issues automatically.

You only act again at: merge approval clicks, Telegram escalations, end-of-project review.

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
- PROJECT_REPO  = (read from env var PROJECT_REPO; if unset, FAIL the whole prompt)
- CACHE_DIR     = $HOME/.hermes-cache/Max_Agency
- ORCH_PROMPT   = $CACHE_DIR/hermes-config/poll-prompts/orchestrator-tick.md
- CODER_PROMPT  = $CACHE_DIR/hermes-config/poll-prompts/coder-tick.md

PROCEDURE:

1. Verify PROJECT_REPO is set. If not, emit FAIL and abort.

2. Verify both prompt files exist. If either is missing, emit FAIL and abort.

3. Register the orchestrator cron job. Use this exact command (substitute $vars):
   hermes -p orchestrator cron add \
     --name "max-agency-orchestrator-tick" \
     --schedule "* * * * *" \
     --prompt-file "$ORCH_PROMPT" \
     --env "PROJECT_REPO=$PROJECT_REPO" \
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
     --env "PROJECT_REPO=$PROJECT_REPO" \
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
8. `env | grep PROJECT_REPO` returns a non-empty value. (PASS/FAIL)

OUTPUT CONTRACT:
- 8 lines, one per check: "CHECK <n>: PASS" or "CHECK <n>: FAIL — <reason>".
- Final line MUST be exactly: BOOTSTRAP_COMPLETE (if all PASS) or BOOTSTRAP_INCOMPLETE (otherwise).

STOP.
```

**Expected last line:** `BOOTSTRAP_COMPLETE`

---

## Architect kickoff prompt (Claude Code app)

Open Claude Code in any directory. Paste this:

```
You are the Architect of the Max Agency. Your role contract is at https://github.com/Wagner-Maximiliano/Max_Agency/blob/main/agents/architect.md — fetch it (or clone the repo) and follow it exactly. Also read docs/MDP.md, docs/AMA.md, CODING_STANDARDS.md, and Highlevel_Plan_V2.0.md from the same repo.

Project brief:
<one paragraph stating goal, constraints, deadline if any>

Target repo: <owner/repo>   (the empty GitHub repo you just created; this is the PROJECT repo, not the agency)

Begin your workflow. Ask up to 5 clarifying questions in one batched message, then produce PLAN.md and submit it for CTO review.
```

---

## Cheat sheet

| Prompt | When | Paste into |
|---|---|---|
| H1 | Once, first-time agency setup | Hermes default profile |
| H2 | Once after H1; also re-run when you change `PROJECT_REPO` | Hermes default profile |
| H3 | Once, immediately after H2 | Hermes default profile |
| Architect kickoff | Once per new project | Claude Code Windows app |

After first-time H1–H3 setup, normal operation is: set `PROJECT_REPO` → re-paste H2 (to update cron env) → paste Architect kickoff. That's it.

---

## Troubleshooting

| Symptom | Action |
|---|---|
| `hermes profile create` says "exists" | Fine, H1 handles this as `[OK skipped]`. Move on. |
| H1 fails at step 2c (config copy) | Check `$HOME/.hermes/profiles/<name>/` exists. If not, profile creation failed silently — run `hermes profile create <name>` manually and re-run H1. |
| H2 `--prompt-file` rejected | Your Hermes version uses `--prompt` only. The prompt instructs Hermes to fall back — if it didn't, paste H2 again with explicit "use --prompt fallback for both jobs". |
| H2 FAIL at step 1 (PROJECT_REPO unset) | You forgot to `$env:PROJECT_REPO = "..."` in this shell. Set it, then re-paste H2. |
| H3 CHECK 8 FAIL | Same as above — `PROJECT_REPO` not set in this shell. |
| Cron ticks not firing | `hermes -p orchestrator cron list` — confirm schedule. Check Hermes daemon is running. Inspect `~/.hermes/profiles/orchestrator/escalations.log`. |
| Cron ticks running against the *wrong* project | H2 bakes `PROJECT_REPO` into the cron job env at registration time. Update `$env:PROJECT_REPO`, re-paste H2 to re-register. |
| Claude Code routine not picking up issues | `Get-ScheduledTask MaxAgency-ClaudeCodeRoutine`. Check History tab. Make sure `claude` CLI is on PATH. |
| Claude Code routine pointing at wrong project | Re-run `register-task.ps1` with the new `-Repo $env:PROJECT_REPO`; it replaces the existing task. |
| Issue picked up by both Hermes and Claude Code | Labels collided. Each issue should have exactly one `assigned:*` label. Fix the label, re-add `ready`. |
| OpenRouter rate-limit errors | Reduce cron frequency: `hermes -p <profile> cron remove …` then re-add with `--schedule "*/5 * * * *"`. |
| "Where do I edit the agency?" | In `C:\Users\lobster\Github_Projects\Max_Agency`. Push via PR. Hermes pulls from GitHub on next cron tick. |
| "Where do I edit the project's code?" | Nowhere — the agents do. You only review PRs. |

---

## What you, the human, do

- **Once per machine:** first-time agency setup (Steps 1–4 above). Maybe an hour.
- **Once per project:** create empty GitHub repo, set `PROJECT_REPO`, paste Architect kickoff. Five minutes.
- **Ongoing:** approve merges. Resolve escalations on Telegram. Kill anything that loops.

Everything else is delegated. If you find yourself doing more than this, the prompts need tightening — file an issue on the agency repo with what felt manual.

---

## Phone workflow

Day-to-day from your phone, using the GitHub mobile app or `github.com` in a browser:

- **Approve merges** — open the PR, scan CTO's `VERDICT: APPROVED` comment + green CI, hit **Merge**.
- **Resolve escalations** — Telegram pings; reply on Telegram, or comment on the linked issue from GitHub.
- **Skim status** — the `State.md` file in the project repo root is the snapshot; the Orchestrator regenerates it every tick.
- **Pause everything** — comment `pause` on any open issue you own, or add label `blocked` from the mobile app. Orchestrator stops dispatching new work for that phase next tick.

You should never need to push code from the phone. If you do, the agents have lost the plot — file an issue describing what they got stuck on.
