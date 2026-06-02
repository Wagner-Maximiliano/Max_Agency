---
name: mdp-project-kickoff
description: "Use when starting, importing, or re-scoping an MDP-managed project. Captures kickoff data, sizing tier, permission mode, roles, risks, and definition of done."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [mdp, kickoff, intake, planning, project-setup]
    related_skills: [mdp-core, mdp-decision-gates, mdp-kanban-health]
---

# MDP Project Kickoff

## Overview

This skill turns a vague project into an MDP-managed workstream. It captures enough context to start safely without overplanning small tasks or underplanning risky work.

Kickoff should be short by default. Scale only when risk, uncertainty, complexity, or impact demands it.

## When to Use

Use this skill when:

- Starting a new project.
- Moving an existing project into MDP governance.
- Re-scoping a project after a major change.
- Creating the first Kanban board or task graph.
- Permission boundaries are unclear.

Do not use this for tiny already-scoped tasks unless the action touches git, production, money, reputation, security, or irreversible changes.

## Required Intake Fields

Capture:

- Project name.
- Human Owner.
- Goal and non-goals.
- Existing project path or new project location.
- Whether repo creation is needed.
- Current repository permission mode.
- Project size tier: Tiny, Small, Medium, or Large.
- Roles involved: PA, COO, CTO, CFO, Operator, Specialist Workers.
- Approval chain.
- Definition of Done.
- Main risks and unknowns.
- Verification expectations.
- Whether GitHub, commits, pushes, deployments, external services, production, live systems, or paid services are allowed.
- Initial Kanban board name and first task set.

## Sizing Tiers

- **Tiny:** checklist only. Use when low risk and easy rollback.
- **Small:** short kickoff. One or a few tasks, simple verification.
- **Medium:** MAP-lite. Needs role routing, decision points, and explicit verification.
- **Large:** full MDP. Needs board, health monitoring, handovers, gates, and multi-role coordination.

Scale by risk, complexity, uncertainty, and impact, not excitement.

## Kickoff Procedure

1. Read the smallest available project pointer.
2. If missing, create or propose an `MDP.md` pointer using no-clobber rules.
3. Determine size tier.
4. Determine permission mode.
5. Identify role leads and approval chain.
6. Define the first safe next action.
7. Create initial Kanban tasks if the project is Medium or Large.
8. Record unresolved questions as blockers, not hidden assumptions.

## Permission Mode Prompt

If permission mode is missing, ask or infer conservatively:

- Mode 0: read-only.
- Mode 1: local edits allowed, no commits.
- Mode 2: local commits allowed, no push.
- Mode 3: bounded remote actions allowed.
- Mode 4: privileged actions, explicit Human Owner approval required.

When in doubt, default to Mode 0 or Mode 1 until clarified.

## Common Pitfalls

1. Creating a big plan for a tiny task.
2. Starting implementation before permission mode is known.
3. Assuming GitHub, commit, push, deployment, or production access is allowed.
4. Missing the Definition of Done.
5. Creating opaque Kanban task titles that only contain IDs.
6. Hiding unknowns instead of turning them into blockers or decision briefs.

## Verification Checklist

- [ ] Goal and non-goals are clear enough to start.
- [ ] Permission mode is recorded.
- [ ] Size tier is recorded with reason.
- [ ] Role owners and approval chain are known.
- [ ] First safe task is identified.
- [ ] Major risks and unknowns are explicit.
- [ ] Kanban board exists or is intentionally not needed.
