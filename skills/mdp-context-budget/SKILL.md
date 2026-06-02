---
name: mdp-context-budget
description: Use when managing token budget, context pressure, subagent prompts, long sessions, or compact handovers in MDP projects.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [mdp, context, tokens, handover, efficiency]
    related_skills: [mdp-handover-restart, mdp-model-cost-governance, mdp-agent-routing]
---

# MDP Context Budget

## Overview

MDP treats context as a project resource. Long projects fail when agents dump too much text, reread broad files unnecessarily, or lose important state before handover. This skill keeps context lean while preserving the facts needed to move safely.

Use small reads, targeted searches, scripts, summaries, and handovers instead of giant context injection.

## When to Use

Use this skill when:

- A task spans many files, agents, or sessions.
- Context is getting large or repetitive.
- Creating prompts for subagents.
- Summarizing project state for Max or another agent.
- Preparing for context compaction or restart.
- Deciding what to read, search, or inject.

## Context Rules

1. Read the smallest file section that can answer the question.
2. Search before reading broad files.
3. Pass paths and line references instead of huge pasted content when the worker can use tools.
4. Use scripts to aggregate counts, statuses, and structured summaries.
5. Do not reread agent bootstrap files unless the task actually needs them.
6. Do not send credentials, secrets, or unnecessary logs into prompts.
7. Before context collapse, produce a handover with active state, decisions, blockers, and restart prompt.

## Subagent Prompt Budget

A good subagent prompt includes:

- Goal.
- Required paths.
- Constraints and forbidden actions.
- Relevant excerpts only.
- Verification required.
- Output format.
- Escalation rule.

A bad prompt includes:

- Whole files when paths would work.
- Repeated background already known to the worker.
- Vague goals.
- No verification expectations.
- No permission boundary.

## Compression Pattern

For project state, compress to:

- Goal.
- Active task.
- Current status.
- Decisions made.
- Files changed.
- Verification done.
- Blockers.
- Next safe action.
- Confidence.
- Human approval needed or not.

## Common Pitfalls

1. **Reading everything just in case.** Start targeted. Expand only when needed.
2. **Pasting massive logs.** Extract failures, paths, commands, and exit codes.
3. **Losing active state before compaction.** Use `mdp-handover-restart` before context pressure becomes critical.
4. **Giving subagents repeated global policy.** Include only what affects their task.
5. **Skipping verification to save tokens.** Verification is not optional when files or systems change.
6. **Keeping stale assumptions.** Recheck current files, git state, or board state when it matters.

## Verification Checklist

- [ ] Searches and reads were targeted.
- [ ] Subagent prompts were scoped and did not include huge unnecessary context.
- [ ] Scripts handled deterministic aggregation where useful.
- [ ] Secrets and irrelevant logs were excluded.
- [ ] A handover exists when context risk is high.
