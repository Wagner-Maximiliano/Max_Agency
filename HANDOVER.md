# Max Agency — Session Handover

**Written:** 2026-06-08  
**Handed to:** Next session  
**Project repo:** `Wagner-Maximiliano/Surviving_The_AI_World`  
**Agency repo (Windows):** `C:\Users\lobster\Github_Projects\Max_Agency`

---

## What happened in this session

This session focused on diagnosing why the orchestrator was burning all 40 turns without completing, and fixing the duplicate-issue bug.

### Changes committed (3 commits on top of `db269dc`)

| Commit | What changed |
|--------|-------------|
| `3301e57` | Revert max_turns 60→40 and timeout 1800→1200 everywhere; remove dead step 0 (sandbox git pull, always fails) and step 3 (rebuild-state via PowerShell, never available in WSL) from orchestrator-tick.md |
| `2501806` | Fix step 8 idempotency: a closed CTO review with `VERDICT: CHANGES REQUIRED` now re-creates a fresh review instead of silently skipping — fixes the post-rework re-review cycle |
| `92ebf83` | Fix duplicate issue creation: kickoff→planned label swap now happens at the **start** of kickoff processing (before any child issues created), not at the end — acts as a mutex against session-compression re-runs |

### Manual actions taken on GitHub

- Closed duplicate issues **#33, #34, #35, #36, #37, #38** (each was a duplicate of #39–#44 created by a double kickoff run)
- Manually created **CTO review issue #48** for PR #31 (glossary re-review after fixes were applied and CI turned green)

---

## Root cause analysis: why orchestrator was burning 40 turns

Three compounding problems:

1. **10 duplicate in-progress issues** — step 7 (reclaim check) was inspecting each one individually, consuming ~15 turns before reaching steps 8-9. Fixed by closing the duplicates AND fixing the kickoff mutex.

2. **Two dead steps at the top of the prompt** — step 0 (git pull in sandbox, path doesn't exist) and step 3 (rebuild-state via PowerShell, not available in WSL) each wasted 2-3 turns per tick for zero benefit. Both removed.

3. **The model itself is the underlying problem** — `nvidia/nemotron-3-super-120b-a12b:free` averages 10–35 seconds per API call. At 40 turns that is 10–15 minutes per tick, longer than the 5-minute tick interval. Ticks queue behind each other. The orchestrator doesn't need a large model — it reads GitHub issues and runs `gh` commands. **This is the #1 priority for the next session.**

---

## Priority 1 — Switch the orchestrator model (BLOCKING)

The free nemotron model is too slow for reliable operation. The fix is to change the model in two places:

**1. Live WSL profile config:**
```bash
wsl -u hermes -- nano ~/.hermes/profiles/orchestrator/config.yaml
# Change: default: nvidia/nemotron-3-super-120b-a12b:free
# To:     default: <new-model-id>
```

**2. Repo template** (keeps setup script in sync):
`hermes-config/profiles/orchestrator/config.yaml` — change `model.default`

**3. Service file ExecStart** (the `-m` flag must also match):
`hermes-config/hermes-orchestrator-tick.service` — change `-m nvidia/nemotron-3-super-120b-a12b:free`

Then patch the live service:
```bash
wsl -u hermes -- bash -c "sed -i 's|nvidia/nemotron-3-super-120b-a12b:free|<new-model-id>|g' ~/.config/systemd/user/hermes-orchestrator-tick.service && systemctl --user daemon-reload"
```

**Recommended model options** (all available on OpenRouter, fast, cheap, good instruction-following):

| Model ID | Why |
|----------|-----|
| `google/gemini-flash-1.5` | Very fast (~1-2s/call), cheap, handles structured prompts well |
| `openai/gpt-4o-mini` | Fast (~2s/call), extremely reliable at following numbered steps |
| `anthropic/claude-haiku-4-5-20251001` | Fast, same family as the coder, strong instruction following |
| `mistralai/mistral-small-3.1-24b-instruct` | Fast free-tier option |

**After switching:** watch the next tick complete cleanly in under 5 minutes via:
```bash
wsl -u hermes -- bash -c "tail -f ~/.hermes/profiles/orchestrator/cron-output.log"
```
Expected: tick header → TICK_OK within 3-4 minutes.

---

## Priority 2 — Close orphaned PR #45

PR [#45](https://github.com/Wagner-Maximiliano/Surviving_The_AI_World/pull/45) (`phase-0/38-readme-contributing`) was opened for issue #38, which was closed this session as a duplicate. The PR is now orphaned.

```bash
gh pr close 45 --repo Wagner-Maximiliano/Surviving_The_AI_World --comment "Closing: linked issue #38 was a duplicate of #44. Work continues on PR #46."
```

---

## Priority 3 — Monitor the active review cycles

Two CTO review issues are in-flight; the Claude Code routine (opus) should pick them up:

| Issue | Reviews | PR | CI | Expected outcome |
|-------|---------|----|----|-----------------|
| **#48** | PR #31 (GLOSSARY) | [#31](https://github.com/Wagner-Maximiliano/Surviving_The_AI_World/pull/31) | ✅ Green | VERDICT: APPROVED → orchestrator auto-merges |
| **#47** | PR #46 (README/CONTRIBUTING) | [#46](https://github.com/Wagner-Maximiliano/Surviving_The_AI_World/pull/46) | ❌ Red | VERDICT: CHANGES REQUIRED → coder fixes Vale CI → re-review |

PR #46 has the same Vale tarball download failure that PR #31 had. The coder already fixed it on the `phase-1/30-glossary` branch — the fix needs to be applied to `phase-0/44-readme-contributing-manuscript` too. The correct fix (from PR #31 commit `5d67447`) is retry logic / follow-redirects in the Vale install step of `.github/workflows/book.yml`.

After #47 routes CHANGES REQUIRED to issue #44:
1. Coder picks up #44 (it will get `in-progress`, no assignee)
2. Coder checks out existing branch `phase-0/44-readme-contributing-manuscript`
3. Fixes Vale download in workflow
4. Pushes → PR #46 CI turns green
5. Issue #44 re-labelled `review`
6. Orchestrator creates new CTO review → APPROVED → auto-merge

---

## Priority 4 — hermes-coder issues #39–#43 (Phase 0 tasks)

Five Phase 0 tasks are `in-progress` for `hermes-coder` with no assignees — Hermes hasn't picked them up yet.

| Issue | Task |
|-------|------|
| #39 | 0/0.1: Repo skeleton + directory layout + ADR stubs |
| #40 | 0/0.2: Pandoc build config (Makefile + defaults, xelatex template) |
| #41 | 0/0.3: Vale styles + proselint config |
| #42 | 0/0.4: GitHub Actions workflow |
| #43 | 0/0.5: Pre-commit hooks |

These depend on #39 (repo skeleton) being done first — #40-#43 all depend on the directory structure existing. If the Hermes coder timer is working, it should pick up #39 first. Check `hermes-coder-tick` timer status:

```bash
wsl -u hermes -- bash -c "systemctl --user list-timers | grep hermes"
wsl -u hermes -- bash -c "tail -20 ~/.hermes/profiles/coder/cron-output.log 2>/dev/null || echo 'no coder log yet'"
```

---

## Current GitHub state (as of ~13:27 CEST 2026-06-08)

### Open issues (9)

| # | Title | Labels | Assignees |
|---|-------|--------|-----------|
| #48 | CTO review: PR #31 (GLOSSARY) | `in-progress`, `phase:1`, `assigned:claude-opus`, `role:cto` | Wagner-Maximiliano |
| #47 | CTO review: PR #46 (README/CONTRIBUTING) | `in-progress`, `phase:0`, `assigned:claude-opus`, `role:cto` | Wagner-Maximiliano |
| #44 | 0/0.6: README + CONTRIBUTING | `review`, `phase:0`, `assigned:claude-haiku`, `role:coder` | — |
| #43 | 0/0.5: Pre-commit hooks | `in-progress`, `phase:0`, `assigned:hermes-coder`, `role:coder` | — |
| #42 | 0/0.4: GitHub Actions workflow | `in-progress`, `phase:0`, `assigned:hermes-coder`, `role:coder` | — |
| #41 | 0/0.3: Vale styles | `in-progress`, `phase:0`, `assigned:hermes-coder`, `role:coder` | — |
| #40 | 0/0.2: Pandoc build config | `in-progress`, `phase:0`, `assigned:hermes-coder`, `role:coder` | — |
| #39 | 0/0.1: Repo skeleton | `in-progress`, `phase:0`, `assigned:hermes-coder`, `role:coder` | Wagner-Maximiliano |
| #30 | phase-1/1.7: GLOSSARY | `review`, `phase:1`, `assigned:claude-haiku`, `role:coder` | — |

### Open PRs

| # | Branch | CI | Notes |
|---|--------|----|-------|
| [#46](https://github.com/Wagner-Maximiliano/Surviving_The_AI_World/pull/46) | phase-0/44-readme-contributing-manuscript | ❌ Red | Vale CI failure — awaiting CTO #47 verdict |
| [#45](https://github.com/Wagner-Maximiliano/Surviving_The_AI_World/pull/45) | phase-0/38-readme-contributing | ✅ Green | **Orphaned** — close it |
| [#31](https://github.com/Wagner-Maximiliano/Surviving_The_AI_World/pull/31) | phase-1/30-glossary | ✅ Green | Awaiting CTO #48 verdict |

---

## Monitoring commands

```bash
# Orchestrator tick output (last result)
wsl -u hermes -- bash -c "tail -20 ~/.hermes/profiles/orchestrator/cron-output.log"

# Live orchestrator activity
wsl -u hermes -- bash -c "strings ~/.hermes/profiles/orchestrator/logs/agent.log | grep 'API call\|Turn ended' | tail -10"

# Timer schedule
wsl -u hermes -- bash -c "systemctl --user list-timers | grep hermes"

# Claude Code routine log (Windows)
# Use PowerShell: Get-Content C:\Users\lobster\Github_Projects\Max_Agency\logs\claude-routine.log -Tail 30

# GitHub state
gh issue list --repo Wagner-Maximiliano/Surviving_The_AI_World --state open --limit 20
gh pr list --repo Wagner-Maximiliano/Surviving_The_AI_World --state open
```

---

## Key file paths

| What | Path |
|------|------|
| Orchestrator tick prompt | `hermes-config/poll-prompts/orchestrator-tick.md` |
| Orchestrator profile config (repo template) | `hermes-config/profiles/orchestrator/config.yaml` |
| Orchestrator service template | `hermes-config/hermes-orchestrator-tick.service` |
| Live orchestrator profile config (WSL) | `~/.hermes/profiles/orchestrator/config.yaml` |
| Live service file (WSL) | `~/.config/systemd/user/hermes-orchestrator-tick.service` |
| Orchestrator cron log (WSL) | `~/.hermes/profiles/orchestrator/cron-output.log` |
| Claude Code routine script | `claude-code-routine/run-tick.ps1` |
| Claude Code routine log | `logs/claude-routine.log` |

---

## What NOT to touch

- Do NOT change `goals.max_turns` above 40 — the problem is the model speed, not the turn count.
- Do NOT re-create issues #30, #39–#44, #47, #48 — they are all legitimately open.
- Do NOT close PRs #31 or #46 — they are active work.
- Do NOT re-apply the kickoff mutex fix — it is already committed (`92ebf83`).

---

*End of handover.*
