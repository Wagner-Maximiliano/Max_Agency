# Human Runbook — Max Agency

> **New here?** Open `max-agency-flow-diagram(Production).html` in a browser — an illustrated, plain-language walkthrough of how the system works and how to install it. This runbook is the precise step-by-step.

---

## Quick Start

There are **three things you ever do**. Find your situation and jump to it:

| Your situation | Go to |
|---|---|
| 🖥️ **Fresh machine** — Max Agency is not installed yet | **Part 1 — Set up a new environment** |
| 🆕 **Machine is ready, starting a brand-new project** (empty repo, no plan yet) | **Part 2A — New project from scratch** |
| ♻️ **Machine is ready, returning to a project that already has labels + a plan** | **Part 2B — Existing project** |

**Supported platform: Windows 11 + WSL2 only.** Mac/Linux is out of scope.

> Do Part 1 **once per machine**. After that you only ever do Part 2A or Part 2B — never Part 1 again.

---

Two halves below: **Reference** (how it works — read once) and **Instructions** (what to do — follow every time).

---

# Reference

## What this is

An autonomous multi-agent dev team coordinated through GitHub. You paste prompts to set it up and kick off projects; the agents do the rest. You approve a few merges and resolve the occasional escalation.

## The three locations

| # | Name | Where | You touch it |
|---|---|---|---|
| 1 | **Agency repo** — the engine (prompts, skills, scripts) | Windows: `$env:USERPROFILE\Github_Projects\Max_Agency` + a mirror on your GitHub account | Rarely — only to upgrade the engine |
| 2 | **Hermes cache** — auto-pulled copy of the agency | WSL: `~/.hermes-cache/Max_Agency` | Never (managed automatically) |
| 3 | **Project repo** — one per project (PLAN, issues, code) | A GitHub repo | Create it; then approve PRs |

## Key facts

- **Hermes runs in WSL; Claude Code runs in Windows.** They are separate processes — an env var set in one is invisible to the other. That's why the project repo is baked into Hermes via the **H2** prompt *and* passed to the Windows routine via **register-task.ps1** separately. **Both must point at the same repo slug**, spelled identically.
- **The agency is the toolkit; a project repo is the workshop.** Never copy files between them.
- **Project repos live on GitHub; you don't clone them locally.** The agents do all work through GitHub.

## Binding docs (every agent reads these)

`Highlevel_Plan_V2.0.md` · `CODING_STANDARDS.md` · `docs/AMA.md` · `skills/`

## Label scheme (canonical)

Every project issue carries four label groups. Pollers find work by **intersecting all four** — a missing label makes an issue invisible to its agent.

| Group | Values | Owner |
|---|---|---|
| `assigned:<model>` | `hermes-coder`, `claude-haiku`, `claude-sonnet`, `claude-opus` | PLAN.md Model Roster decides |
| `role:<role>` | `architect`, `cto`, `coder` | Set when the issue is created |
| `phase:<N>` | `phase:0` through `phase:7` | From PLAN.md |
| State | `backlog` → `ready` → `in-progress` → `review` (plus `blocked`, `kickoff`, `planned`) | Orchestrator manages transitions |

**Hermes coder** polls `in-progress + assigned:hermes-coder + role:coder`.
**Claude Code routine** polls `in-progress + assigned:claude-*` and reads `role:*` to load the right agent file (`agents/architect.md`, `agents/cto.md`, or `agents/coder.md`).

> ⚠️ **CTO review issues** (whether for a PR or for a PLAN) **must** carry `role:cto` + `in-progress` + `assigned:claude-opus`. The mechanics script labels PR reviews correctly on its own; for PLAN reviews the Architect does it (see `agents/architect.md` Step 3). An issue labelled `review` or missing `role:cto` will **never** be picked up.

There are **no separate CTO/Architect routines**. One Claude Code routine handles all three roles, switching behavior based on the issue's `role:*` label. Hermes only ever runs as coder.

**Model-per-label enforcement:** the Claude Code routine is launched by `run-tick.ps1`, which peeks the queue, reads the next claimable issue's `assigned:claude-<model>` label, and starts Claude with the matching `--model` (`haiku`/`sonnet`/`opus`). This makes the PLAN.md cost roster real, not cosmetic.

## How a task flows (the lifecycle)

Every unit of work is a GitHub issue that walks through labelled states. The Orchestrator moves it left-to-right; coders and the CTO do the work at each stage.

```
kickoff ─▶ backlog ─▶ ready ─▶ in-progress ─▶ review ─▶ closed
   │          │          │           │            │
 Architect  deps      deps        a coder       a CTO         ↑ auto-merged (most cases)
 PLAN.md    pending   cleared     claims it,     reviews,     ↑ OR you approve (if CTO says "needs human")
 parsed                           opens a PR     posts VERDICT
```

1. **kickoff** — the approved `PLAN.md` is parsed; one issue per task is created (`backlog` or `ready`), each tagged `assigned:<model>` + `role:<role>` + `phase:<N>`.
2. **backlog → ready** — when an issue's `Depends-on:` issues are all closed, the Orchestrator promotes it.
3. **ready → in-progress** — the Orchestrator dispatches it (posts a comment, flips the label). Now a coder can see it.
4. **a coder claims it** — adds itself as assignee, makes a branch, commits, opens a PR (`Closes #N`), flips the issue to `review`.
5. **CTO review** — the Orchestrator opens a dedicated `role:cto` issue pointing at the PR. The CTO reads the diff + CI, posts a verdict with two parts: `VERDICT: APPROVED | CHANGES REQUIRED | ESCALATE` and `HUMAN-REVIEW: YES | NO`.
6. **routing** — `APPROVED + HUMAN-REVIEW: NO` → Orchestrator **auto-merges** the PR, no human needed. `APPROVED + HUMAN-REVIEW: YES` → you get a plain-language Telegram message asking for sign-off. `CHANGES REQUIRED` → the task bounces back to `in-progress` for the coder. `ESCALATE` → it comes to you.
7. **closed** — either auto-merged by the Orchestrator, or merged by you after human sign-off.

**When you get a Telegram message asking to merge,** it will look like this — just reply with a number:

```
👀 YOUR EYES NEEDED — Your Project Name

What the team built: Added a new page to the book
Why I need you: This changes how the book looks — needs your eyes first

📸 See the changes here: https://github.com/...
🤖 AI quality check: Passed ✅

Reply with a number:
1️⃣ MERGE — looks good, ship it
2️⃣ REJECT — send it back
3️⃣ EXPLAIN — break it down for me
```

**Safety gates:** the CTO is always a *different* agent instance than the coder it reviews, and `HUMAN-REVIEW: YES` changes always wait for you before merging.

---

# Instructions

## Part 1 — Set up a new environment (install Max Agency)

**Do this once per machine.** It installs the engine but does not start any project — that's Part 2.

### 1.1 — Prerequisites (install these first)

| Tool | Install |
|---|---|
| Windows 11 + WSL2 | `wsl --install` in Admin PowerShell, then reboot |
| Claude Desktop + Claude Code CLI | https://claude.ai/download, then `npm install -g @anthropic-ai/claude-code` |
| Hermes | Follow the Hermes install guide (provides the `hermes` CLI in WSL) |
| GitHub CLI | https://cli.github.com — then `gh auth login` (HTTPS + browser) **in both Windows PowerShell and WSL** |

**Check (run in both Windows PowerShell and a WSL terminal):**

```
claude --version     # prints a version
gh --version         # prints a version
gh auth status       # shows your account as active
```

> `gh` must be authenticated **separately** in Windows and WSL — they are different installs. The Windows routine and Hermes each use their own `gh`.

### 1.2 — Get Max Agency onto your machine and your GitHub

Hermes clones the agency from your GitHub account, so the repo must exist there. Two cases:

**If you forked / already have `Max_Agency` on your GitHub:** just clone it to Windows.

```powershell
git clone https://github.com/<your-github-username>/Max_Agency "$env:USERPROFILE\Github_Projects\Max_Agency"
```

**If you only have the files locally (no GitHub copy yet):** create an empty `Max_Agency` repo on github.com, then publish.

```powershell
cd "$env:USERPROFILE\Github_Projects\Max_Agency"
git init -b main
git remote add origin https://github.com/<your-github-username>/Max_Agency.git
git add .; git commit -m "initial: max agency baseline"; git push -u origin main
```

**Check:** `git -C "$env:USERPROFILE\Github_Projects\Max_Agency" remote -v` shows your origin URL.

### 1.3 — Create the Hermes profiles (prompt H1)

Open a **WSL** terminal:

```bash
hermes chat
```

Edit the `PUBLIC_REPO` line in **H1** (Section C) to your GitHub username, paste it, and wait for `BOOTSTRAP_H1_COMPLETE`. This creates the `orchestrator` and `coder` profiles and clones the agency into `~/.hermes-cache/Max_Agency`.

> H1 is project-agnostic — it sets up the engine, not a project. You point at a specific project later in Part 2 (prompt H2).

### 1.4 — Deploy the systemd timers

This copies the canonical service files and the mechanics script into the live Hermes install and starts the every-5-minutes timers. **Without this step Hermes is installed but asleep.**

```bash
git -C ~/.hermes-cache/Max_Agency pull --rebase && \
  bash ~/.hermes-cache/Max_Agency/hermes-config/deploy.sh
```

**Check:** `systemctl --user list-timers | grep hermes` shows `hermes-orchestrator-tick.timer` and `hermes-coder-tick.timer` with a `NEXT` time.

> Re-run this command any time you update the agency repo. It is safe to run repeatedly.
>
> **Key files it deploys:**
> - `orchestrator-mechanics.sh` — the deterministic queue manager (heartbeat, promote, dispatch, reclaim, CTO-review creation, verdict routing). The orchestrator LLM calls this every tick.
> - `hermes-orchestrator-tick.service` / `hermes-coder-tick.service` — the systemd units that fire every 5 minutes.

### 1.5 — Configure the Hermes model

Each agent's model lives **in its own profile config** — orchestrator and coder are independent.

```bash
nano ~/.hermes/profiles/orchestrator/config.yaml   # orchestrator model
nano ~/.hermes/profiles/coder/config.yaml          # coder model
```

Find the `model:` block and set `default` (and `max_tokens` if needed):

```yaml
model:
  default: openai/gpt-4o-mini      # ← a fast, cheap default; change to taste
  max_tokens: 16384                # keep ≤ your provider credit balance
```

The change takes effect on the **next tick** — no restart needed. The global `~/.hermes/config.yaml` model is a fallback for other Hermes usage and is not used by these profiles.

| Provider | Auth (in `~/.hermes/.env`) | Notes |
|---|---|---|
| `openrouter` | `OPENROUTER_API_KEY` | Routes to any model — recommended |
| `openai-codex` | ChatGPT OAuth (`hermes auth`) | Shares ChatGPT quota; can 429 under load |
| `nous` | Nous Portal OAuth | |
| `zai` | `ZAI_API_KEY` | Z.AI / GLM |

### 1.6 — Telegram for phone approvals (nothing to set up)

Max Agency does **not** set up or manage its own Telegram bot. If your Hermes installation already has a Telegram gateway configured (`TELEGRAM_BOT_TOKEN` + `TELEGRAM_HOME_CHANNEL` in WSL `~/.hermes/.env`), the orchestrator automatically reuses it for `HUMAN-REVIEW: YES` merge requests and escalations — no action needed.

If Hermes has no Telegram gateway configured, escalations are written to `~/.hermes/profiles/orchestrator/escalations.log` instead — the system still works, you just have to read the log. Don't create a separate bot just for Max Agency; if you want phone approvals, set up Telegram for Hermes itself (see Hermes's own docs) and Max Agency will pick it up automatically on the next tick.

**Environment is ready.** Now do Part 2 to start a project.

---

## Part 2 — Start or resume a project

Pick the path that matches your project.

### Part 2A — New project from scratch

A brand-new, empty repo with no labels and no plan yet.

#### 2A.1 — Create an empty GitHub repo

github.com → New repository → name it → **no** README / .gitignore / licence → Create. Note the slug, e.g. `your-name/my-app`.

#### 2A.2 — Create the canonical labels

The pipeline routes entirely on labels, so the repo needs them before anything runs. **Windows PowerShell:**

```powershell
cd "$env:USERPROFILE\Github_Projects\Max_Agency"
.\scripts\setup-project.ps1 -Repo "<your-github-username>/<your-project-repo>"
```

This creates all 22 labels (`assigned:*`, `role:*`, `phase:0–7`, the state labels) and sets light branch protection on `main`.

**Check:** `gh label list --repo <your-github-username>/<your-project-repo>` lists `role:cto`, `assigned:claude-opus`, `in-progress`, etc.

> Branch protection may warn "main may not exist yet" on a fresh empty repo — harmless. The labels are what matter, and they are created regardless.

#### 2A.3 — Point Hermes at the project (prompt H2)

**WSL:** in `hermes chat`, edit the first line of **H2** (Section C) to your project slug, paste it, wait for `BOOTSTRAP_H2_COMPLETE`. This writes `PROJECT_REPO=<slug>` into `~/.hermes/.env`.

#### 2A.4 — Point the Claude Code routine at the project

**Windows PowerShell** (use the **same slug** as 2A.3):

```powershell
cd "$env:USERPROFILE\Github_Projects\Max_Agency\claude-code-routine"
.\register-task.ps1 -Repo "<your-github-username>/<your-project-repo>" -ProjectPath "$env:USERPROFILE\Github_Projects\Max_Agency" -IntervalMinutes 5
```

**Check:** `Get-ScheduledTask -TaskName "MaxAgency-ClaudeCodeRoutine"` shows the task as `Ready`.

#### 2A.5 — Kick off the Architect

Open **Claude Desktop**, start a new conversation, and paste the **Architect kickoff** prompt (Section C) with your one-paragraph brief and the project slug filled in. Answer its questions (one at a time), then approve `PLAN.md` when it asks. From there the agents take over.

---

### Part 2B — Existing project

A repo that **already has** the Max Agency labels and a plan/history (e.g. you're switching back to it, or set it up on a new machine). The labels already exist, so you do **not** re-run `setup-project.ps1`, and the plan already exists, so you usually do **not** re-run the Architect.

#### 2B.1 — Point Hermes at the project (prompt H2)

**WSL:** in `hermes chat`, edit the first line of **H2** (Section C) to the existing project slug, paste it, wait for `BOOTSTRAP_H2_COMPLETE`. This re-points `~/.hermes/.env` at this repo.

#### 2B.2 — Point the Claude Code routine at the project

**Windows PowerShell** (same slug as 2B.1; `-Force` is built in, so it safely overwrites the previous registration):

```powershell
cd "$env:USERPROFILE\Github_Projects\Max_Agency\claude-code-routine"
.\register-task.ps1 -Repo "<your-github-username>/<your-project-repo>" -ProjectPath "$env:USERPROFILE\Github_Projects\Max_Agency" -IntervalMinutes 5
```

#### 2B.3 — Resume (and, if needed, start the next phase)

Both runtimes are now pointed at the project. Within ~5 minutes the timers and routine pick up wherever the project left off — open `in-progress` issues get worked, open CTO reviews get verdicts, approved PRs merge.

- **Verify it's alive:** `systemctl --user list-timers | grep hermes` (WSL) and check the Windows routine log at `...\Max_Agency\logs\claude-routine.log`.
- **If a label got into a bad state** (e.g. a CTO review missing `role:cto`), fix it per the ⚠️ note in the Label scheme above.
- **To start a new phase** that isn't open yet, paste the **Architect kickoff** prompt (Section C) describing the next phase. The Architect writes/updates `PLAN.md`, submits it for CTO review, and on your go-ahead the Orchestrator creates that phase's issues.

---

## C. Prompts

### H1

Edit `PUBLIC_REPO` (line 2 of CONSTANTS) to your GitHub username before pasting.

```
You are bootstrapping the Max Agency on this machine. Follow these steps in order. Do NOT improvise. Do NOT skip steps. Print [OK] or [FAIL: <reason>] after each numbered step.

CONSTANTS:
- PUBLIC_REPO = https://github.com/<your-github-username>/Max_Agency
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

### H2

Edit the first line, then paste. Use the GitHub `owner/repo` slug — not a URL, not a local path (e.g. `Wagner-Maximiliano/Surviving_The_AI_World`).

```
PROJECT_REPO = Wagner-Maximiliano/REPLACE-WITH-YOUR-PROJECT-REPO

You are continuing Max Agency bootstrap. H1 must have completed.

Extract PROJECT_REPO from the first line (the part after "= "). Substitute it for __PROJECT_REPO__ on line 5 of the script below, then run the script exactly as written. Do not modify anything else.

  python3 - <<'PY'
import os, subprocess, sys, re
from pathlib import Path

PROJECT_REPO = '__PROJECT_REPO__'
HOME         = Path.home()
CACHE_DIR    = HOME / '.hermes-cache' / 'Max_Agency'
ORCH_PROMPT  = CACHE_DIR / 'hermes-config' / 'poll-prompts' / 'orchestrator-tick.md'
CODER_PROMPT = CACHE_DIR / 'hermes-config' / 'poll-prompts' / 'coder-tick.md'
ORCH_NAME    = 'max-agency-orchestrator-tick'
CODER_NAME   = 'max-agency-coder-tick'
ENV_PATH     = HOME / '.hermes' / '.env'

def fail(step, reason):
    print(f'[{step} FAIL: {reason}]')
    print('BOOTSTRAP_H2_ABORT')
    sys.exit(0)

def run(cmd):
    p = subprocess.run(cmd, text=True, capture_output=True)
    return p.returncode, p.stdout, p.stderr

def find_job_id(profile, name):
    _, out, _ = run(['hermes', '-p', profile, 'cron', 'list', '--all'])
    current_id = None
    for line in out.splitlines():
        m = re.match(r'\s+([0-9a-f]{10,16})\s+\[', line)
        if m:
            current_id = m.group(1)
        n = re.match(r'\s+Name:\s+(.+)', line)
        if n and n.group(1).strip() == name and current_id:
            return current_id
    return None

# Step 1
if PROJECT_REPO in ('REPLACE-WITH-YOUR-PROJECT-REPO', '__PROJECT_REPO__', ''):
    fail(1, 'PROJECT_REPO is still the placeholder — edit the first line')
print(f'[1 OK: PROJECT_REPO={PROJECT_REPO}]')

# Step 2
if not ORCH_PROMPT.is_file():
    fail(2, f'missing {ORCH_PROMPT} — re-run H1')
if not CODER_PROMPT.is_file():
    fail(2, f'missing {CODER_PROMPT} — re-run H1')
print('[2 OK]')

# Step 3: Bake PROJECT_REPO into ~/.hermes/.env
if ENV_PATH.exists():
    content = ENV_PATH.read_text(encoding='utf-8')
    content = re.sub(r'^PROJECT_REPO=.*\n?', '', content, flags=re.MULTILINE)
    content = content.rstrip('\n') + f'\nPROJECT_REPO={PROJECT_REPO}\n'
    ENV_PATH.write_text(content, encoding='utf-8')
else:
    ENV_PATH.write_text(f'PROJECT_REPO={PROJECT_REPO}\n', encoding='utf-8')
print(f'[3 OK: PROJECT_REPO written to {ENV_PATH}]')

# Step 4: Register orchestrator cron (replace if already exists)
job_id = find_job_id('orchestrator', ORCH_NAME)
if job_id:
    run(['hermes', 'cron', 'remove', job_id])
rc, out, err = run(['hermes', 'cron', 'add', '* * * * *',
                    ORCH_PROMPT.read_text(encoding='utf-8'),
                    '--name', ORCH_NAME, '--profile', 'orchestrator'])
if rc != 0:
    fail(4, (out + err).strip() or 'hermes cron add failed for orchestrator')
print('[4 OK: orchestrator cron registered]')

# Step 5: Register coder cron (replace if already exists)
job_id = find_job_id('coder', CODER_NAME)
if job_id:
    run(['hermes', 'cron', 'remove', job_id])
rc, out, err = run(['hermes', 'cron', 'add', '* * * * *',
                    CODER_PROMPT.read_text(encoding='utf-8'),
                    '--name', CODER_NAME, '--profile', 'coder'])
if rc != 0:
    fail(5, (out + err).strip() or 'hermes cron add failed for coder')
print('[5 OK: coder cron registered]')

# Step 6: Verify
_, orch_list, _ = run(['hermes', '-p', 'orchestrator', 'cron', 'list'])
_, coder_list, _ = run(['hermes', '-p', 'coder', 'cron', 'list'])
if ORCH_NAME not in orch_list:
    fail(6, f'{ORCH_NAME} not found in orchestrator cron list')
if CODER_NAME not in coder_list:
    fail(6, f'{CODER_NAME} not found in coder cron list')
if f'PROJECT_REPO={PROJECT_REPO}' not in ENV_PATH.read_text(encoding='utf-8'):
    fail(6, 'PROJECT_REPO not confirmed in ~/.hermes/.env')
print(f'[6 OK: both cron jobs active; PROJECT_REPO={PROJECT_REPO} in .env]')
print('BOOTSTRAP_H2_COMPLETE')
PY

OUTPUT CONTRACT:
- Print script output verbatim.
- Final line MUST be BOOTSTRAP_H2_COMPLETE (all steps pass) or BOOTSTRAP_H2_ABORT (any fail).
- STOP immediately after the script exits.
```

> **Note:** H2 registers Hermes built-in cron jobs (steps 4–5). These are stored inside Hermes but **do not fire automatically on this setup** — the real runtime is the **systemd user timers** from `deploy.sh` (Part 1, step 1.4). The H2 cron registration exists only for environments where the Hermes gateway runs cron natively, and to bake `PROJECT_REPO` into `~/.hermes/.env`. The systemd timers (already running from Part 1) read that `PROJECT_REPO` on their next tick.

### H3 (verify setup — optional)

Paste any time to confirm the environment + current project are wired correctly.

```
You are continuing Max Agency bootstrap. H1 and H2 must have completed. Run all checks below. Print PASS or FAIL for each.

CHECKS:

1. `hermes profile list` includes both orchestrator and coder.
2. `hermes -p orchestrator cron list` shows max-agency-orchestrator-tick.
3. `hermes -p coder cron list` shows max-agency-coder-tick.
4. `cat $HOME/.hermes/profiles/orchestrator/SOUL.md` starts with "# Orchestrator — Soul".
5. `cat $HOME/.hermes/profiles/coder/SOUL.md` starts with "# Coder (Hermes side) — Soul".
6. `ls $HOME/.hermes/profiles/orchestrator/skills/ | wc -l` is at least 1.
7. `ls $HOME/.hermes/profiles/coder/skills/ | wc -l` is at least 1.
8. `grep PROJECT_REPO ~/.hermes/.env` returns a non-empty, non-placeholder value. Print the value.

OUTPUT CONTRACT:
- 8 lines: "CHECK <n>: PASS" or "CHECK <n>: FAIL — <reason>".
- Final line MUST be exactly: BOOTSTRAP_COMPLETE (if all PASS) or BOOTSTRAP_INCOMPLETE (otherwise).

STOP.
```

### Architect kickoff (Claude Desktop)

Replace `<your-github-username>` in the URL with yours (or paste the agency repo URL you published in Part 1).

```
You are the Architect of the Max Agency. Your role contract is at https://github.com/<your-github-username>/Max_Agency/blob/main/agents/architect.md — fetch it (or clone the repo) and follow it exactly. Also read docs/AMA.md, CODING_STANDARDS.md, and Highlevel_Plan_V2.0.md from the same repo.

Project brief:
<one paragraph: goal, constraints, deadline if any>

Target repo: <owner/repo>   # the project repo — NOT the agency repo

Begin your workflow. Ask up to a maximum of 10 clarifying questions, one question at a time with multiple numbered choices to select from, then produce PLAN.md and submit it for CTO review.

When you submit for CTO review, you MUST create the review as a GitHub issue in the target repo with labels `role:cto` + `in-progress` + `assigned:claude-opus` + the active `phase:<N>` (this is how the autonomous CTO routine finds it — follow architect.md Step 3 exactly). Do not use the `review` label and do not leave off `role:cto`, or the CTO will never pick it up.
```

---

## D. Teardown (undo everything)

**Claude Code routine** (Windows PowerShell):

```powershell
Unregister-ScheduledTask -TaskName "MaxAgency-ClaudeCodeRoutine" -Confirm:$false
```

**Hermes cron jobs** (WSL — get IDs from `hermes -p orchestrator cron list` and `hermes -p coder cron list`):

```bash
hermes -p orchestrator cron list   # note the hex job ID next to max-agency-orchestrator-tick
hermes cron remove <orchestrator-job-id>
hermes -p coder cron list          # note the hex job ID next to max-agency-coder-tick
hermes cron remove <coder-job-id>
```

**Systemd timers** (WSL — stops the real runtime):

```bash
systemctl --user stop hermes-orchestrator-tick.timer hermes-coder-tick.timer
systemctl --user disable hermes-orchestrator-tick.timer hermes-coder-tick.timer
```

**Hermes profiles** (WSL — only if fully removing):

```bash
hermes profile remove orchestrator
hermes profile remove coder
rm -rf ~/.hermes-cache/Max_Agency
```

---

## E. Cheat sheet

| Action | Where | Steps |
|---|---|---|
| Install on a new machine | — | Part 1 (1.1 → 1.6) |
| Start a brand-new project | — | Part 2A (2A.1 → 2A.5) |
| Return to an existing project | — | Part 2B (2B.1 → 2B.3) |
| Switch which project is active | WSL + Windows | H2 (Hermes) + `register-task.ps1` (routine) with the new slug |
| Verify wiring | WSL | paste H3 |
| Undo | — | Section D |

---

## F. Troubleshooting

| Symptom | Fix |
|---|---|
| H2 FAIL: placeholder | You didn't edit the `PROJECT_REPO = ...` first line. Edit and re-paste. |
| H2 FAIL: prompt files missing | H1 didn't finish. Re-run H1. |
| H3 CHECK 8 FAIL | H2 didn't finish or kept the placeholder. Re-run H2, then H3. |
| Nothing happens after setup | Timers not running. WSL: `systemctl --user list-timers \| grep hermes` — if absent, re-run `deploy.sh` (Part 1, step 1.4). |
| Set `$env:PROJECT_REPO` but Hermes ignores it | Expected — Windows ≠ WSL. For Hermes use H2; for the Claude Code routine use `register-task.ps1`. |
| Claude Code routine logs `NO_WORK` even with open issues | Issue must have `assigned:claude-*` (haiku/sonnet/opus) AND a `role:*` label. Architect/CTO tasks need `role:architect`/`role:cto`. |
| CTO never picks up a review (PR or PLAN) | The review issue is missing `role:cto` or is labelled `review`/`ready` instead of `in-progress`. Fix: `gh issue edit <N> --repo <slug> --add-label role:cto --add-label in-progress --remove-label review`. (PLAN reviews are created by the Architect — see `agents/architect.md` Step 3.) |
| No labels on the project repo | You skipped 2A.2. Run `scripts\setup-project.ps1 -Repo "<slug>"` from Windows. |
| Wrong project being worked | Hermes: re-paste H2 with corrected slug. Windows: re-run `register-task.ps1`. They must match exactly. |
| Routine not picking up issues at all | Windows: `Get-ScheduledTask MaxAgency-ClaudeCodeRoutine` → History. Verify `claude --version` and `gh auth status` both work in PowerShell. |
| Scheduled task opens a visible terminal window | Registered with `LogonType Interactive`. Re-run `register-task.ps1` (now uses `S4U`), or: `$p = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited; Set-ScheduledTask -TaskName "MaxAgency-ClaudeCodeRoutine" -Principal $p` |
| Routine output not visible | Log: `<AgencyPath>\logs\claude-routine.log`. Each entry prefixed `=== TICK <timestamp> \| issue=<N> model=<m> ===`. |
| `register-task.ps1` fails with "positional parameter... GitHub" | PowerShell 5.1 encoding bug — a non-ASCII char in the `.ps1`. Re-pull the agency repo: `git pull`. |
| Both runtimes grab one issue | Issue has two `assigned:*` labels. Reduce to one, re-add `ready`. |
| Hermes coder fires every minute but never picks work | Issue needs all three: `in-progress` + `assigned:hermes-coder` + `role:coder`. |
| Telegram messages never arrive | Max Agency only reuses Hermes's existing gateway — check `grep TELEGRAM ~/.hermes/.env` (in **WSL**, not Windows) for `TELEGRAM_BOT_TOKEN` + `TELEGRAM_HOME_CHANNEL`. If neither is set, escalations go to `~/.hermes/profiles/orchestrator/escalations.log` instead — that's expected, not a bug. |
| Orchestrator logs `NO_REPO` | `~/.hermes/.env` missing `PROJECT_REPO=...`. Re-run H2. |
| Orchestrator queue ops (close merged PRs, CTO review, verdict routing) not happening | These are in `orchestrator-mechanics.sh`, not the LLM. Run it manually to see the error: `PROJECT_REPO=owner/repo bash ~/.hermes/profiles/orchestrator/orchestrator-mechanics.sh`. Check stderr for Python tracebacks or `gh` auth errors. |
| Orchestrator service killed mid-run (`timeout` in journalctl) | `TimeoutStartSec` too low. Re-run `deploy.sh`, or: `sed -i 's/TimeoutStartSec=[0-9]*/TimeoutStartSec=300/' ~/.config/systemd/user/hermes-orchestrator-tick.service && systemctl --user daemon-reload`. |
| Phase task issues never appear after kickoff | The kickoff issue lost its `kickoff` label but no child issues exist — step failed silently. Re-add `kickoff` and watch the next tick; idempotency prevents duplicates. |
| Claude Code routine `401 Invalid authentication credentials` | Claude Code OAuth token expired (~30-day life). Run `claude /login` in PowerShell, sign in. Next tick uses the fresh token. |
| Routine "succeeds" (result 0) but does no work | It needed a `gh` permission it couldn't get headlessly. Confirm `.claude/settings.json` exists in the agency repo with the `gh`/`git` allowlist (ships in the repo — `git pull` if missing). |
| Hermes ticks all log `HTTP 429: usage limit reached` | Provider quota exhausted. Switch model/provider in the profile config — see Part 1, step 1.5. |
| Issue stuck `in-progress` with an assignee but nobody working it | A coder claimed it then died mid-tick (all agents auth as the same GitHub user, so the assignee is a phantom). The reclaim step clears it within ~60 min; to unstick now: `gh issue edit <N> --remove-assignee <user> --remove-label blocked`. |
| Merged PR but its issue stayed open | GitHub's `Closes #N` auto-close is unreliable. The Orchestrator closes it next tick; or close by hand. |

---

## G. Phone workflow

Most PRs merge automatically — you won't hear anything. You only get a message when the AI decided a human should look first (visual changes, things that can't be undone, money/direction decisions).

**When you get a merge request on Telegram:**
- Read the two plain-English lines explaining what changed and why you're being asked.
- Open the PR link to see the changes (GitHub shows a visual diff — green = added, red = removed).
- Reply with **1** to approve, **2** to send back, **3** if you need it explained more.

**When you get a plan go-ahead request** (the CTO approved a PLAN), reply **1** to start the work, **2** to request changes, **3** to have it explained.

**Escalations** (something went wrong or the AI is stuck) — reply on Telegram or comment on the linked GitHub issue.

**Status** — read `State.md` in the project repo root.

**Pause a phase** — add the `blocked` label to an issue from the GitHub mobile app.

You should never push code from your phone. If you feel you need to, file an issue — it means the agents got stuck.
