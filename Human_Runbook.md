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

### A4 — Install the Claude Code routine

Windows PowerShell (fill in your project repo):

```powershell
$env:PROJECT_REPO = "Wagner-Maximiliano/your-project-repo"
cd "C:\Users\lobster\Github_Projects\Max_Agency\claude-code-routine"
.\register-task.ps1 -Repo $env:PROJECT_REPO -ProjectPath "C:\Users\lobster\Github_Projects\Max_Agency" -IntervalMinutes 10
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
.\register-task.ps1 -Repo $env:PROJECT_REPO -ProjectPath "C:\Users\lobster\Github_Projects\Max_Agency" -IntervalMinutes 10
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

Edit the first line, then paste:

```
PROJECT_REPO = Wagner-Maximiliano/REPLACE-WITH-YOUR-PROJECT-REPO

You are continuing Max Agency bootstrap. H1 must have completed. Follow these steps. Print [OK] or [FAIL: <reason>] after each.

CONSTANTS (use the PROJECT_REPO value from the first line of this message):
- CACHE_DIR     = $HOME/.hermes-cache/Max_Agency
- ORCH_PROMPT   = $CACHE_DIR/hermes-config/poll-prompts/orchestrator-tick.md
- CODER_PROMPT  = $CACHE_DIR/hermes-config/poll-prompts/coder-tick.md

PROCEDURE:

1. Confirm PROJECT_REPO from the first line. Print its value. If it is still "REPLACE-WITH-YOUR-PROJECT-REPO", emit FAIL and abort.

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
   If --prompt-file is unsupported, read the file and pass contents via --prompt.

4. Register the coder cron job:
   hermes -p coder cron add \
     --name "max-agency-coder-tick" \
     --schedule "* * * * *" \
     --prompt-file "$CODER_PROMPT" \
     --env "PROJECT_REPO=$PROJECT_REPO" \
     --env "MAX_AGENCY_CACHE=$CACHE_DIR" \
     --timeout 1500
   Same --prompt fallback if needed.

5. Run `hermes -p orchestrator cron list` and `hermes -p coder cron list`. Confirm each shows exactly one job and print the PROJECT_REPO baked into each.

OUTPUT CONTRACT:
- One [OK] / [FAIL: …] line per step.
- Final line MUST be: BOOTSTRAP_H2_COMPLETE
- On any failure, emit BOOTSTRAP_H2_ABORT and stop.

STOP after step 5.
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
8. The orchestrator cron job env has a non-empty, non-placeholder PROJECT_REPO. Print the value.

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

**Hermes cron jobs** (WSL):

```bash
hermes -p orchestrator cron remove max-agency-orchestrator-tick
hermes -p coder cron remove max-agency-coder-tick
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
| H2 `--prompt-file` rejected | Add "use --prompt fallback for both jobs" to the top of H2 and re-paste. |
| Cron not firing | WSL: `hermes -p orchestrator cron list`, check `hermes status`, see `~/.hermes/profiles/orchestrator/escalations.log`. |
| Wrong project | Hermes: re-paste H2 with corrected repo. Windows: re-run `register-task.ps1`. |
| Routine not picking up issues | Windows: `Get-ScheduledTask MaxAgency-ClaudeCodeRoutine` → History. Ensure `claude` is on PATH. |
| Both runtimes grab one issue | Issue has two `assigned:*` labels. Fix to one, re-add `ready`. |
| OpenRouter rate limits | WSL: remove the cron job, re-add with `--schedule "*/5 * * * *"`. |

---

## G. Phone workflow

- **Approve merges** — open PR, check CTO `VERDICT: APPROVED` + green CI, tap Merge.
- **Escalations** — reply on Telegram or comment on the linked issue.
- **Status** — read `State.md` in the project repo root.
- **Pause a phase** — add label `blocked` to an issue from the GitHub app.

You should never push code from your phone. If you need to, file an issue — the agents got stuck.
