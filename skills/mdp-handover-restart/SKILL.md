---
name: mdp-handover-restart
description: "Use when an MDP project needs human handover, technical handover, context-limit protection, restart prompts, ownership transfer, or session continuity."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [mdp, handover, restart, context, continuity]
    related_skills: [mdp-core, mdp-kanban-health, mdp-verification-rollback]
---

# MDP Handover and Restart

## Overview

MDP projects must survive context limits, agent changes, pauses, and restarts. A good handover lets the next session continue without making Max repeat the project history.

This skill defines the required handover package.

## When to Use

Use this skill when:

- Context is approaching the project threshold, around 160k tokens by default.
- Context quality is getting poor.
- A session is ending before the project is complete.
- Ownership changes from one role or agent to another.
- A project is paused or restarted.
- A large decision or milestone just completed.

Do not wait until the model is already confused. Handover early enough to be accurate.

## Required Outputs

Create three outputs:

1. **Human summary handover**: short, plain-language status for the Human Owner.
2. **Technical agent handover**: precise implementation state for the next agent.
3. **Copy-paste restart prompt**: message the Human Owner can paste into a fresh session.

Use project templates when available:

- `templates/human-handover.md`
- `templates/technical-handover.md`
- `templates/restart-prompt.md`

## Human Summary Handover

Include:

- Current goal.
- What was completed.
- Current status.
- What is blocked.
- Decisions made.
- What Max needs to know.
- Recommended next action.

Keep it readable and concise.

## Technical Agent Handover

Include:

- Active task or board.
- Files changed.
- Commands run.
- Tests and validation results.
- Known warnings.
- Current permission mode.
- Open blockers.
- Pending gates or approvals.
- Rollback notes.
- Exact next actions.
- Things the next agent must not do.

## Restart Prompt

The restart prompt should tell the next session:

- Project path.
- Ordered files to read first.
- Current board/task state and board of record.
- Secondary routing or technical context sources when they differ from the board.
- Current objective.
- Constraints and permission mode.
- Important notes that would prevent stale assumptions.
- First action to take.
- Actions to avoid.
- Approval gates still in force.

## Restart-Resume Execution Pass

When Max explicitly asks to resume from a restart prompt, do not stop after reloading context.

Use the first pass to convert the routing view into active execution state:

1. Read the restart prompt and every required pointer in the listed order.
2. Respect the declared permission mode before doing anything else.
3. Identify the board of record and any separate routing view or technical context spine.
4. Move the first approved workstream from routing order into one explicit active lane on the board or equivalent source of truth.
5. Create or refresh one focused proof, checklist, or validation plan for that active lane instead of adding more broad status prose.
6. Prefer updating existing sources of truth over creating duplicate status documents.
7. Refresh the handover package so the next restart reflects the new active lane and exact next action.

## Draft and Review Rule

A lower-cost Operator may draft handovers. The PA reviews and accepts only when confidence is at least 95 percent. If confidence is lower, request targeted improvements.

## Common Pitfalls

1. Writing one giant handover that is bad for both humans and agents.
2. Forgetting the restart prompt.
3. Omitting permission mode or hard gates.
4. Claiming tests passed without command evidence.
5. Saving project-specific temporary details into long-term memory instead of handover files.
6. Waiting until context collapse has already damaged accuracy.
7. Treating a restart as a read-only exercise instead of an execution handoff.
8. Letting board state, routing state, and handover state drift apart.

## Verification Checklist

- [ ] Human summary exists and is readable.
- [ ] Technical handover exists and includes exact state.
- [ ] Restart prompt exists and is copy-paste ready.
- [ ] Permission mode and hard gates are included.
- [ ] Verification and rollback state are included.
- [ ] Active lane and next action are explicit.
- [ ] Handover location is communicated to the Human Owner.
