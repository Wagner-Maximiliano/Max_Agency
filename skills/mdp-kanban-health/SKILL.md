---
name: mdp-kanban-health
description: "Use when managing MDP Kanban tasks, worker status, blockers, watchdogs, project health, stale work, or autonomous project momentum."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [mdp, kanban, health, monitoring, watchdog, execution]
    related_skills: [mdp-core, mdp-decision-gates, mdp-handover-restart]
---

# MDP Kanban and Project Health

## Overview

Kanban is the MDP work coordination layer. It tracks tasks, owners, state, blockers, evidence, and next actions. The Human Owner should not have to monitor whether the system is alive.

This skill governs task hygiene and proactive health checks.

## When to Use

Use this skill when:

- Creating, updating, completing, blocking, or unblocking MDP tasks.
- Coordinating multiple agents or role lanes.
- A worker is stale, silent, crashed, or looping.
- A board has no ready work but unfinished tasks remain.
- Project state changes between live, waiting, paused, completed, or archived.
- Setting up a watchdog or health report.

Do not use Kanban for tiny one-message tasks unless tracking is useful.

## Task Title Standard

Use human-readable titles:

`<Phase/Area>: <action/outcome> - <artifact/scope>`

Good:

- `Kickoff: capture permission mode - MDP pilot`
- `CTO review: inspect skill install safety - Hermes profile`

Bad:

- `M10-N`
- `fix stuff`
- `task 3`

Keep raw IDs internally, but make list views understandable.

## Task Comment Standard

Important task comments should include:

- What changed.
- Files or artifacts touched.
- Verification performed.
- Result and warnings.
- Blockers or risks.
- Next action.
- Confidence.
- Safety notes and permission mode relevance.

Complete a task only with evidence.

## Project Health Signals

Watch for:

- New blocked tasks.
- Running tasks without heartbeat.
- Silent agents.
- No ready/running tasks while project is live.
- Repeated failures.
- Provider, API, token, or auth errors.
- Stale claims.
- Missing verification evidence.
- Long-running tasks with no output.
- Context collapse risk without handover.

Use scripts and structured status before model reasoning where practical.

## Structured Status Fields

For large MDP projects, maintain or infer:

- Task state.
- Owner role.
- Last heartbeat.
- Phase.
- Blocker.
- Confidence.
- Last verification.
- Next action.
- Human input needed.
- Project state: live, waiting, paused, completed, archived.

## Watchdog Behavior

A watchdog should:

1. Inspect board state.
2. Detect stuck or inconsistent state.
3. Dispatch safe ready work if allowed.
4. Recover crashed tasks only when confidence is high enough and rollback/safety is clear.
5. Notify the PA with compact evidence when Human Owner input or lead review is needed.
6. Stay quiet when there is nothing useful to report.

## Common Pitfalls

1. Completing cards because work seems done without evidence.
2. Letting a project stall because one task is blocked while safe parallel work exists.
3. Creating task titles that humans cannot understand.
4. Using comments as a dump instead of concise operational evidence.
5. Not distinguishing live, waiting, paused, completed, and archived states.
6. Spamming the Human Owner instead of routing through PA/lead roles first.

## Verification Checklist

- [ ] Board state matches actual work state.
- [ ] Task titles are human-readable.
- [ ] Blockers include required unblock information.
- [ ] Completed tasks include evidence.
- [ ] Stale or silent workers are detected.
- [ ] Safe parallel work is considered.
- [ ] Human Owner notifications are compact and necessary.
