# Human Runbook — Max Agency

Two parts: **Reference** (how it works — read once, skip later) and **Instructions** (what to do — follow every time).

---

# Reference

## What this is

An autonomous multi-agent dev team coordinated through GitHub. You paste prompts to set it up and kick off projects; the agents do the rest. You approve merges and resolve escalations.

## The three locations

| # | Name | Where | You touch it |
|---|---|---|---|
| 1 | **Agency repo** — the engine (prompts, skills, scripts) | Windows: `C:\Users\lobster\Github_Projects\Max_Agency` + GitHub mirror | Rarely — only to upgrade the agency |
| 2 | **Hermes cache** — auto-pulled copy of the agency | WSL: `~/.hermes-cache/Max_Agency` | Never |
| 3 | **Project repo** — one per project (PLAN, issues, code) | A new empty GitHub repo | Create it; then approve PRs |

## Key facts

- **Hermes runs in WSL; Claude Code runs in Windows.** They are separate — an env var set in one is invisible to the other. That's why the project repo is typed into the H2 prompt directly, not read from a Windows variable.
- **The agency is the toolkit; a project repo is the workshop.** Never copy files between them.
- **Project repos are empty + remote-only.** You never clone them locally; the agents work via GitHub.

## Binding docs (every agent reads these)

`Highlevel_Plan_V2.0.md` · `CODING_STANDARDS.md` · `docs/MDP.md` · `docs/AMA.md` · `skills/`

## Label scheme (canonical)

Every project issue carries four label groups. Pollers find work by intersecting all four.

| Group | Values | Owner |
|---|---|---|
| `assigned:<model>` | `hermes-coder`, `claude-haiku`, `claude-sonnet`, `claude-opus` | PLAN.md Model Roster decides |
| `role:<role>` | `architect`, `cto`, `coder` | Orchestrator infers from task title at kickoff |
| `phase:<N>` | `phase:0` through `phase:7` | From PLAN.md |
| State | `backlog` → `ready` → `in-progress` → `review` (plus `blocked`, `kickoff`, `planned`) | Orchestrator manages transitions |

**Hermes coder** polls `in-progress + assigned:hermes-coder + role:coder`.
**Claude Code routine** polls `in-progress + assigned:claude-*` and reads `role:*` to load the right agent file (`agents/architect.md`, `agents/cto.md`, or `agents/coder.md`).

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

> 📘 **New to all this?** Read `docs/How_Max_Agency_Works.pdf` — a fully illustrated, plain-language walkthrough of everything below.

---

# Instructions

## A. First-time setup (once per machine)

### A1 — Publish the agency repo

Windows PowerShell:

```powershell
cd "C:\Users\lobster\Github_Projects\Max_Agency"
git init -b main
git remote add origin https://github.com/Wagner-Maximiliano/Max_Agency.git
git add .; git commit -m "initial: max agency baseline"; git push -u origin main
```

**Check:** `git remote -v` shows the origin URL. (Skip this step if the repo is already on GitHub.)

### A2 — Set Windows env var (Claude Code routine only)

Windows PowerShell:

```powershell
notepad $PROFILE
```

Paste at the bottom, save, close, then reopen PowerShell:

```powershell
$env:MAX_AGENCY_CACHE = "$env:USERPROFILE\.hermes-cache\Max_Agency"
# Telegram (optional):
# $env:TELEGRAM_BOT_TOKEN = "..."
# $env:TELEGRAM_CHAT_ID   = "..."
```

**Check:** new PowerShell window → `$env:MAX_AGENCY_CACHE` prints the path.
**Undo:** reopen `notepad $PROFILE`, delete those lines, save.

### A3 — Bootstrap Hermes

WSL terminal:

```bash
hermes chat
```

Paste **H1**, wait for `BOOTSTRAP_H1_COMPLETE`. Edit the first line of **H2** with your project repo, paste, wait for `BOOTSTRAP_H2_COMPLETE`. Paste **H3**, wait for `BOOTSTRAP_COMPLETE`.

**Undo:** see "Teardown" below.

### A3b — Set orchestrator turn budget

The orchestrator service must use `--max-turns 20`. With the default of 10, steps 7.5–9 (CTO issue creation, verdict routing, auto-merge) are skipped each tick.

If you re-install Hermes on WSL, patch the service file after H3 completes:

```bash
# Set turn budget to 40 and raise service timeout to 20 min
sed -i 's/--max-turns [0-9]*/--max-turns 40/' \
  ~/.config/systemd/user/hermes-orchestrator-tick.service
sed -i 's/TimeoutStartSec=[0-9]*/TimeoutStartSec=1200/' \
  ~/.config/systemd/user/hermes-orchestrator-tick.service
systemctl --user daemon-reload
systemctl --user restart hermes-orchestrator-tick.timer
```

**Check:** `grep max-turns ~/.config/systemd/user/hermes-orchestrator-tick.service` should show `--max-turns 20`.

---

### A4 — Configure the Hermes model

Each agent has its model set **in its own profile config** — orchestrator and coder can be changed independently without touching the global Hermes config.

WSL:

```bash
nano ~/.hermes/profiles/orchestrator/config.yaml   # orchestrator model
nano ~/.hermes/profiles/coder/config.yaml          # coder model
```

Find the `model:` block and change `default` and/or `max_tokens`:

```yaml
model:
  default: nvidia/nemotron-3-super-120b-a12b:free   # ← change this line
  max_tokens: 16384                                  # keep ≤ OpenRouter credit balance
```

The global `~/.hermes/config.yaml` model is **not used** by these profiles — it remains as a fallback for other Hermes usage.

**Supported providers** (from the comments at the bottom of `~/.hermes/config.yaml`):

| Provider | Auth | Notes |
|---|---|---|
| `openrouter` | `OPENROUTER_API_KEY` in `~/.hermes/.env` | Routes to any model — recommended |
| `openai-codex` | ChatGPT OAuth (`hermes auth`) | Shares ChatGPT account quota; hits 429 under load |
| `nous` | Nous Portal OAuth | |
| `zai` | `ZAI_API_KEY` | Z.AI / GLM |

The change takes effect on the **next tick** — no timer restart needed.

> **Note:** The Claude Code routine (Windows) picks its model from the issue's `assigned:claude-*` label — that's a separate, per-task setting controlled by PLAN.md. Hermes and Claude Code are independent; configuring one does not affect the other.

---

### A5 — Install the Claude Code routine

**Prerequisites (one-time installs):**

```powershell
# 1. Claude Code CLI
npm install -g @anthropic-ai/claude-code
claude --version   # should print a version

# 2. GitHub CLI  (https://cli.github.com)
gh --version       # should print a version
gh auth login      # authenticate once; choose HTTPS + browser
gh auth status     # should show your account as active
```

Windows PowerShell (fill in your project repo):

```powershell
$env:PROJECT_REPO = "Wagner-Maximiliano/your-project-repo"
cd "C:\Users\lobster\Github_Projects\Max_Agency\claude-code-routine"
.\register-task.ps1 -Repo $env:PROJECT_REPO -ProjectPath "C:\Users\lobster\Github_Projects\Max_Agency" -IntervalMinutes 5
```

**Check:** `Get-ScheduledTask -TaskName "MaxAgency-ClaudeCodeRoutine"` shows the task.
**Undo:** `Unregister-ScheduledTask -TaskName "MaxAgency-ClaudeCodeRoutine" -Confirm:$false`

---

## B. Start a new project (each time)

### B1 — Create an empty GitHub repo

github.com → New repository → name it → **no** README/gitignore/licence → Create.

### B2 — Point Hermes at it

WSL: edit the first line of **H2** to your new repo, paste it into `hermes chat`. Wait for `BOOTSTRAP_H2_COMPLETE`.

### B3 — Point the Claude Code routine at it

Windows PowerShell:

```powershell
$env:PROJECT_REPO = "Wagner-Maximiliano/your-new-repo"
cd "C:\Users\lobster\Github_Projects\Max_Agency\claude-code-routine"
.\register-task.ps1 -Repo $env:PROJECT_REPO -ProjectPath "C:\Users\lobster\Github_Projects\Max_Agency" -IntervalMinutes 5
```

### B4 — Kick off the Architect

Claude Code app, any directory: paste the **Architect kickoff** prompt with your brief and repo filled in. Answer its questions, approve `PLAN.md` when asked. Done — the agents take over.

---

## C. Prompts

### H1

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

### H3 (verify setup)

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

### Architect kickoff (Claude Code app)

```
You are the Architect of the Max Agency. Your role contract is at https://github.com/Wagner-Maximiliano/Max_Agency/blob/main/agents/architect.md — fetch it (or clone the repo) and follow it exactly. Also read docs/MDP.md, docs/AMA.md, CODING_STANDARDS.md, and Highlevel_Plan_V2.0.md from the same repo.

Project brief:
<one paragraph: goal, constraints, deadline if any>

Target repo: <owner/repo>   (the empty repo you just created — the PROJECT repo, not the agency)

Begin your workflow. Ask up to 5 clarifying questions in one batched message, then produce PLAN.md and submit it for CTO review.
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

**Hermes profiles** (WSL — only if fully removing):

```bash
hermes profile remove orchestrator
hermes profile remove coder
rm -rf ~/.hermes-cache/Max_Agency
```

**Windows env var:** `notepad $PROFILE`, delete the lines, save.

---

## E. Cheat sheet

| Action | Where | Command / prompt |
|---|---|---|
| First setup | — | A1 → A2 → A3 → A4 |
| New project | — | B1 → B2 → B3 → B4 |
| Re-run prompts | WSL | `hermes chat` |
| Verify | WSL | paste H3 |
| Undo | — | Section D |

---

## F. Troubleshooting

| Symptom | Fix |
|---|---|
| H2 FAIL: placeholder | You didn't edit the `PROJECT_REPO = ...` first line. Edit and re-paste. |
| H2 FAIL: prompt files missing | H1 didn't finish. Re-run H1. |
| H3 CHECK 8 FAIL | H2 didn't finish or kept the placeholder. Re-run H2, then H3. |
| Set `$env:PROJECT_REPO` but Hermes ignores it | Expected — Windows ≠ WSL. For Hermes use H2; for Claude Code routine use `register-task.ps1`. |
| Cron not firing | WSL: `hermes -p orchestrator cron list`, check `hermes status`, see `~/.hermes/profiles/orchestrator/escalations.log`. |
| Wrong project | Hermes: re-paste H2 with corrected repo. Windows: re-run `register-task.ps1`. |
| Routine not picking up issues | Windows: `Get-ScheduledTask MaxAgency-ClaudeCodeRoutine` → History. Verify `claude --version` and `gh auth status` both work. |
| `register-task.ps1` fails with "positional parameter... GitHub" | PowerShell 5.1 encoding bug — the `.ps1` file has a non-ASCII character (em-dash). Re-pull the latest agency repo: `git pull`. |
| Both runtimes grab one issue | Issue has two `assigned:*` labels. Fix to one, re-add `ready`. |
| Hermes coder firing every minute but never picks work | Check the issue has all three: `in-progress` + `assigned:hermes-coder` + `role:coder`. Coder only handles `role:coder`. |
| Claude Code routine logs `NO_WORK` even with open issues | Issue must have `assigned:claude-*` (haiku/sonnet/opus) AND a `role:*` label. Architect/CTO tasks need `role:architect`/`role:cto`. |
| Orchestrator logs `TICK_FAIL step:missing-rebuild-state` | `powershell.exe` is unavailable in the WSL sandbox. The step is now best-effort and non-fatal — but if you see it repeatedly, run `scripts/rebuild-state.ps1` manually from Windows PowerShell occasionally to refresh State.md. |
| Orchestrator logs `NO_REPO` | `~/.hermes/.env` missing `PROJECT_REPO=...`. WSL: `cat ~/.hermes/.env`, add the line if missing, then `systemctl --user restart hermes-orchestrator-tick.timer`. |
| Orchestrator completes steps 1–7 but never creates CTO review issues or routes verdicts (steps 7.5–9 skipped) | Service file has too few turns. WSL: `sed -i 's/--max-turns [0-9]*/--max-turns 40/' ~/.config/systemd/user/hermes-orchestrator-tick.service && systemctl --user daemon-reload`. See § A3b. |
| Orchestrator service killed mid-run (`Failed with result 'timeout'` in journalctl) | `TimeoutStartSec` too low. WSL: `sed -i 's/TimeoutStartSec=[0-9]*/TimeoutStartSec=1200/' ~/.config/systemd/user/hermes-orchestrator-tick.service && systemctl --user daemon-reload`. |
| Phase task issues never appear after kickoff | Issue #2 (or your kickoff issue) has the `kickoff` label removed but no child issues exist — the orchestrator's step 4 failed silently. Re-add the `kickoff` label and watch the next tick; idempotency check prevents duplicates. |
| OpenRouter rate limits | WSL: get job ID from `hermes -p orchestrator cron list`, `hermes cron remove <id>`, re-run H2 (change `* * * * *` to `*/5 * * * *` in the prompt). |
| Claude Code routine fails with `401 Invalid authentication credentials` | The Claude Code OAuth token expired (~30-day life). Run `claude /login` in a PowerShell window, sign in, done. The scheduled task picks up the fresh token next tick. |
| Claude Code routine "succeeds" (result 0) but does no work | The routine asked for `gh` permission it couldn't get headlessly. Confirm `.claude/settings.json` exists in the agency repo with the `gh`/`git` allowlist (it ships in the repo — `git pull` if missing). |
| Hermes ticks all log `HTTP 429: usage limit reached` | Your provider's quota is exhausted. Switch to a free/API-billed provider: edit `~/.hermes/config.yaml` → `model.provider: openrouter` + set a free model. See § A4. |
| Hermes ticks log `model not supported` or similar | Wrong model ID for the configured provider. Edit `~/.hermes/config.yaml` → correct `model.default`, then wait for next tick. See § A4. |
| Issue stuck `in-progress` with an assignee but nobody working it | A coder claimed it then died mid-tick (every agent auths as the same GitHub user, so the assignee is a phantom). The Orchestrator's reclaim step clears it automatically within ~60 min; to unstick now, `gh issue edit <N> --remove-assignee <user> --remove-label blocked`. |
| Merged PR but its issue stayed open | GitHub's `Closes #N` auto-close is unreliable. The Orchestrator's step 7.5 closes it on the next tick; or close it by hand. |
| Profile cron jobs never execute (gateway ignores them) | On this machine, Hermes profile-cron isn't auto-run by the gateway — we use **systemd user timers** instead (`hermes-orchestrator-tick.timer`, `hermes-coder-tick.timer`). Check `systemctl --user list-timers`. |

---

## G. Phone workflow

Most PRs are merged automatically — you won't hear anything. You only get a message when the AI decided a human needs to look first (visual changes, things that can't be undone, etc.).

**When you get a merge request on Telegram:**
- Read the two plain-English lines explaining what changed and why you're being asked
- Open the PR link to see the changes (GitHub shows a visual diff — green = added, red = removed)
- Reply with: **1** to approve, **2** to send back, **3** if you need it explained more

**Escalations** (something went wrong or the AI is stuck) — reply on Telegram or comment on the linked GitHub issue.

**Status** — read `State.md` in the project repo root.

**Pause a phase** — add label `blocked` to an issue from the GitHub app.

You should never push code from your phone. If you need to, file an issue — the agents got stuck.
