# Max Agency — Session Handover

**Written:** 2026-06-08  
**Handed to:** Next session  
**Project repo:** `Wagner-Maximiliano/Surviving_The_AI_World`  
**Agency repo (Windows):** `C:\Users\lobster\Github_Projects\Max_Agency`

---

## What happened in this session

This session focused on production readiness: hermes-cache auto-pull, end-to-end verification, improved logging, and making the Windows scheduled task run silently.

### Changes committed (commit `86ed86f`)

| File | What changed |
|------|-------------|
| `hermes-config/poll-prompts/orchestrator-tick.md` | Step 0 added: pull Max_Agency cache at tick start |
| `hermes-config/hermes-orchestrator-tick.service` | NEW — service file template in repo (ExecStart + TimeoutStartSec=1200) |
| `claude-code-routine/run-tick.vbs` | NEW — wscript.exe launcher so Windows task runs with no visible console window |
| `claude-code-routine/run-tick.ps1` | Output redirected to `logs/claude-routine.log` with tick headers |
| `claude-code-routine/register-task.ps1` | Uses wscript.exe+run-tick.vbs as action; LogonType Interactive (window suppressed by vbs) |
| `Human_Runbook.md` | A3b updated with new ExecStart patch steps; adds troubleshooting rows for window/log issues |

### Live system changes (WSL service file)

The `/home/hermes/.config/systemd/user/hermes-orchestrator-tick.service` ExecStart was updated to:
```bash
ExecStart=/bin/bash -c 'L=/home/hermes/.hermes/profiles/orchestrator/cron-output.log; echo "=== TICK $(date -Iseconds) ===" >> "$L"; git -C /home/hermes/.hermes-cache/Max_Agency pull --rebase 2>&1 | grep -v "^Already up to date" >> "$L" || true; /home/hermes/.local/bin/hermes -p orchestrator chat -m nvidia/nemotron-3-super-120b-a12b:free -q "$(cat /home/hermes/.hermes-cache/Max_Agency/hermes-config/poll-prompts/orchestrator-tick.md)" -Q --accept-hooks --yolo --max-turns 40 2>&1 | tail -5 >> "$L"'
```

This is the same ExecStart as the repo template. `systemctl --user daemon-reload` was run.

### Windows scheduled task

The `MaxAgency-ClaudeCodeRoutine` task was updated to use `wscript.exe` + `run-tick.vbs` as the launcher. It fires every 5 minutes and writes to `C:\Users\lobster\Github_Projects\Max_Agency\logs\claude-routine.log`.

---

## Current state — what is already working

| System | State |
|--------|-------|
| `run-tick.ps1` line 62 | Has `--dangerously-skip-permissions` ✅ |
| WSL Hermes orchestrator service | `--max-turns 40`, `TimeoutStartSec=1200` ✅ |
| Windows Scheduled Task | Runs every 5 min via wscript.exe (no window), writes to log ✅ |
| Per-profile model config | Both orchestrator and coder use nemotron:free via OpenRouter ✅ |
| hermes-cache auto-pull | Service ExecStart pulls Max_Agency before each tick ✅ |
| Issue body template | 4-section format committed ✅ |
| Rework loop fix | `poll-and-pickup.md` coder checks existing branch, reads all comments ✅ |

---

## Critical path issue: hermes terminal sandbox

**Important for debugging:** The Hermes terminal toolset runs commands with `~` resolving to the **sandbox home** at `/home/hermes/.hermes/profiles/orchestrator/home/`, NOT the actual `/home/hermes/`. So:

- `~/.hermes-cache/` in tool calls → `/home/hermes/.hermes/profiles/orchestrator/home/.hermes-cache/`
- The PROJECT_REPO clone lives at: `~/.hermes/profiles/orchestrator/home/.hermes-cache/Wagner-Maximiliano/Surviving_The_AI_World/` ✅ (correct)
- `~/.hermes-cache/Max_Agency/` does NOT exist in the sandbox — step 0 in orchestrator-tick.md fails silently (non-fatal, `|| true`)
- The ExecStart git pull uses absolute path `/home/hermes/.hermes-cache/Max_Agency/` (correct)

---

## Current state of Surviving_The_AI_World

As of 2026-06-08 ~11:53 CEST:

### Open issues
- **#30** `phase:1, assigned:claude-haiku, role:coder` — no state label — GLOSSARY task in limbo (should be `in-progress` after orchestrator routes CHANGES REQUIRED from #32)
- **#32** `in-progress, assigned:claude-opus, role:cto` — CTO review for PR #31 — has `VERDICT: CHANGES REQUIRED` comment — orchestrator should route and close
- **#33, #39** `0/0.1: Repo skeleton` — duplicated (orchestrator created same task twice)
- **#34, #40** `0/0.2: Pandoc` — duplicated
- **#35, #41** `0/0.3: Vale styles` — duplicated
- **#36, #42** `0/0.4: GitHub Actions` — duplicated
- **#37, #43** `0/0.5: Pre-commit hooks` — duplicated
- **#38, #44** `review` — README+CONTRIBUTING — PRs #45, #46 open (also duplicated)

### Open PRs
- **#31**: `phase-1/30-glossary` — CHANGES REQUIRED (trailing newline + Vale CI fix)
- **#45**: `phase-0/38-readme-contributing`
- **#46**: `phase-0/44-readme-contributing-manuscript`

### Orchestrator tick in progress
- Session `20260608_113834` started at 11:38 CEST, API call #20+ at 11:53 CEST
- Expected to: route CHANGES REQUIRED from #32 → #30, dispatch Phase 0 tasks, handle new PRs

---

## What the next session must do

### Priority 1 — Verify end-to-end routing closes

After the 11:38 tick completes (~11:55-12:05 CEST), check:
1. Is issue #32 closed?
2. Does issue #30 now have `in-progress` label and no assignee?
3. Does the cron-output.log show `TICK_OK`?

If issue #32 is NOT closed and #30 is still in limbo, the orchestrator's step 9 (verdict routing) may need debugging. In that case, manually close #32 and re-add `in-progress` to #30, then remove its assignee, and watch the next Claude Code tick pick up #30.

### Priority 2 — Resolve duplicate Phase 0 issues

Issues #33–#43 are duplicates of an earlier set (#39–#44 range). The orchestrator created them twice from the same PLAN.md task table. You need to:
- Close the older duplicates (keep the lower-numbered ones) OR
- Let the orchestrator handle them (its idempotency check should prevent further duplication)

Consider adding a `kickoff-handled` idempotency guard so this can't happen again.

### Priority 3 — Monitor GLOSSARY rework

After issue #30 gets `in-progress`, the Claude Code routine should pick it up (haiku model). The new `poll-and-pickup.md` tells the coder to:
1. Check for existing branch (`phase-1/30-glossary` exists)
2. Read ALL comments (the CHANGES REQUIRED list from #32's comment)
3. Fix: add trailing newline, fix Vale CI in `.github/workflows/book.yml`
4. Push to existing branch (PR #31 auto-updates)
5. Re-label as `review`

Watch that this rework cycle closes cleanly.

### Priority 4 — jq installation in WSL

```bash
wsl -u hermes -- bash -c "sudo apt-get install -y jq"
```

This prevents the orchestrator from wasting turns on `| jq '...'` pipe failures.

---

## Monitoring commands

```bash
# Orchestrator log
wsl -u hermes -- bash -c "tail -20 ~/.hermes/profiles/orchestrator/cron-output.log"

# Live agent activity
wsl -u hermes -- bash -c "tail -f ~/.hermes/profiles/orchestrator/logs/agent.log"

# Claude Code routine log
Get-Content C:\Users\lobster\Github_Projects\Max_Agency\logs\claude-routine.log -Tail 20

# GitHub state
gh issue list --repo Wagner-Maximiliano/Surviving_The_AI_World --state open --limit 20
gh pr list --repo Wagner-Maximiliano/Surviving_The_AI_World --state open
```

---

## Reference: key file paths

| What | Path |
|------|------|
| Claude Code routine launch script | `C:\Users\lobster\Github_Projects\Max_Agency\claude-code-routine\run-tick.ps1` |
| Claude Code silent launcher | `C:\Users\lobster\Github_Projects\Max_Agency\claude-code-routine\run-tick.vbs` |
| Claude Code routine log | `C:\Users\lobster\Github_Projects\Max_Agency\logs\claude-routine.log` |
| Claude Code coder/CTO prompt | `C:\Users\lobster\Github_Projects\Max_Agency\claude-code-routine\poll-and-pickup.md` |
| Orchestrator tick prompt | `C:\Users\lobster\Github_Projects\Max_Agency\hermes-config\poll-prompts\orchestrator-tick.md` |
| Orchestrator systemd service (WSL) | `~/.config/systemd/user/hermes-orchestrator-tick.service` |
| Hermes global config (WSL) | `~/.hermes/config.yaml` |
| Orchestrator profile config (WSL) | `~/.hermes/profiles/orchestrator/config.yaml` |
| Coder profile config (WSL) | `~/.hermes/profiles/coder/config.yaml` |
| Max_Agency cache — actual home (WSL) | `/home/hermes/.hermes-cache/Max_Agency/` |
| Max_Agency cache — sandbox home (WSL) | `/home/hermes/.hermes/profiles/orchestrator/home/.hermes-cache/` |
| Project repo clone — sandbox (WSL) | `/home/hermes/.hermes/profiles/orchestrator/home/.hermes-cache/Wagner-Maximiliano/Surviving_The_AI_World/` |
| Orchestrator cron log | `/home/hermes/.hermes/profiles/orchestrator/cron-output.log` |
| Orchestrator heartbeat | `/home/hermes/.hermes/profiles/orchestrator/heartbeat.txt` |
| Agency repo on Windows | `C:\Users\lobster\Github_Projects\Max_Agency` |

---

## What NOT to touch

- Do NOT re-apply the `--dangerously-skip-permissions` fix — it is already committed.
- Do NOT change the orchestrator model config — it's in profile configs and working.
- Do NOT re-create issues #30 or #32 — they need to be routed by the orchestrator.
- Do NOT change the Windows Scheduled Task command line manually — use `register-task.ps1` to regenerate.

---

*End of handover.*
