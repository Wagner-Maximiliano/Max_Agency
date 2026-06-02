---
name: mdp-verification-rollback
description: "Use when an MDP task changes files, config, workflow, infrastructure, data, or behavior and needs verification evidence, warnings, rollback planning, or safety notes."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [mdp, verification, rollback, safety, evidence, quality]
    related_skills: [mdp-core, mdp-decision-gates, mdp-kanban-health]
---

# MDP Verification and Rollback

## Overview

MDP work is not done because an agent says it is done. It is done when the change is verified, warnings are recorded honestly, rollback is understood, and the task evidence is clear.

This skill applies to meaningful implementation, configuration, documentation-system, workflow, or automation changes.

## When to Use

Use this skill when:

- Files, configs, scripts, skills, workflows, repo settings, deployments, or data may change.
- A Kanban task is about to be completed.
- Installing skills or changing Hermes behavior.
- A rollback path is required before execution.
- Verification results need to be recorded.
- There are warnings or non-blocking issues.

Do not use this for pure read-only exploration unless it produces an operational decision.

## Pre-Execution Rollback Plan

Before meaningful execution, identify:

- What will change.
- Files, configs, data, or external systems affected.
- How to undo it.
- Whether rollback is automatic, manual, or impossible.
- Verification command after rollback.
- Who approves rollback if things go wrong.

If rollback is impossible or risky, raise decision risk and consider Human Owner approval.

## Verification Record

Record:

- Command or check run.
- Working directory.
- Result.
- Exit code when available.
- Warnings.
- Known non-blocking issues.
- Remaining risk.
- Confidence.

For file changes, also record changed files or artifact paths.

## File Safety Rule

- Never silently overwrite files.
- Check existence before creating new files.
- Prefer targeted patches for existing files.
- If overwriting is intentional, ensure the user approved the scope or create a backup first.
- On case-insensitive filesystems, check for case collisions like `AGENTS.md` vs `agents.md`.

## Completion Standard

A task can be marked complete only when:

1. Required work is done.
2. Verification is run or explicitly impossible with reason.
3. Warnings are documented.
4. Rollback is documented.
5. Permission mode was respected.
6. Evidence is attached to Kanban, handover, or final response.

## Common Pitfalls

1. Saying should work instead of running verification.
2. Hiding warnings because the main check passed.
3. Forgetting rollback until after something fails.
4. Overwriting files without checking for existence.
5. Treating documentation changes as risk-free when they affect agent behavior.
6. Completing Kanban tasks without evidence.

## Verification Checklist

- [ ] Change scope is clear.
- [ ] Rollback path is documented before risky execution.
- [ ] Verification command/check was run or impossibility is explained.
- [ ] Exit code/result is recorded.
- [ ] Warnings and non-blocking issues are recorded.
- [ ] Permission mode was respected.
- [ ] Evidence is ready for Kanban/task/final report.
