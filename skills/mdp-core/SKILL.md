---
name: mdp-core
description: "Use when entering or operating any MDP-managed project. Loads the small always-read operating core and routes to deeper MDP skills only when needed."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [mdp, orchestration, project-management, governance, operating-system]
    related_skills: [mdp-project-kickoff, mdp-decision-gates, mdp-kanban-health, mdp-handover-restart, mdp-verification-rollback]
---

# MDP Core

## Overview

MDP, Massive Development Plan, is an operating layer for running projects with human ownership, role-based AI agents, Kanban execution, decision gates, verification, rollback, and handovers.

This is the small always-read core. Keep it lean. Load deeper MDP skills only when the current action needs them.

## When to Use

Use this skill when:

- Starting work in an MDP-managed repository.
- Seeing an `MDP.md` project pointer.
- Coordinating multiple roles, agents, or Kanban tasks.
- Deciding whether to plan, execute, escalate, verify, or hand over.
- Bringing an existing project under MDP governance.

Do not use this as a replacement for domain-specific technical skills. Load the relevant technical skill too.

## Core Operating Rules

1. Human Owner is final authority.
2. PA / Orchestrator owns intake, routing, momentum, synthesis, and communication.
3. COO / Decision Coordinator owns major operational, strategic, cross-agent, reputation, business, and life-impact decisions.
4. CTO owns technical architecture, engineering quality, implementation strategy, infrastructure, and production readiness.
5. CFO owns finance, budgets, pricing, subscriptions, investments, and cost tradeoffs.
6. Operator owns bounded scans, summaries, artifact inventories, formatting, and low-risk support work.
7. Specialist Workers execute scoped tasks under the relevant lead role.
8. Planning depth scales with risk, complexity, uncertainty, and impact.
9. Scripts handle deterministic or repeatable logic. LLMs handle ambiguity, synthesis, judgment, and decisions.
10. Use the narrowest practical toolset and model for the job.
11. Respect the declared repository permission mode before touching files, git, GitHub, deployments, external services, or production systems.
12. Never silently overwrite files. Prefer patching existing files. For new files, check for collisions first.
13. Meaningful changes require verification evidence and a rollback path.
14. The Human Owner is not the monitoring system. Agents and scripts must surface project health issues proactively.
15. Keep context lean. Load deeper protocols on demand.

## Skill Routing

Load these deeper skills when needed:

- `mdp-project-kickoff`: project intake, sizing, permission mode, definition of done.
- `mdp-decision-gates`: confidence scoring, escalation, approval briefs, blocked decisions.
- `mdp-kanban-health`: Kanban task hygiene, worker status, blockers, watchdogs, project health.
- `mdp-handover-restart`: human and technical handovers plus restart prompt.
- `mdp-verification-rollback`: verification records, warnings, rollback planning.

## Minimal Project Discovery

When entering a project:

1. Look for `MDP.md` first.
2. Read only the smallest project pointer needed to understand scope.
3. Identify permission mode, current board, current phase, and active blockers.
4. Load deeper MDP skills only for the current action.
5. If the project is not yet MDP-managed, use `mdp-project-kickoff`.

## Common Pitfalls

1. Repeating the whole MDP protocol in every prompt. Use the project pointer and skills instead.
2. Treating confidence as permission. High confidence does not bypass Human Owner gates for high-impact or irreversible work.
3. Letting the board stall while waiting for one blocked task. Look for safe parallel work first.
4. Making file changes without checking collision or rollback.
5. Completing Kanban cards without evidence.
6. Loading every MDP file into context instead of routing to the relevant skill.

## Verification Checklist

- [ ] Project pointer or kickoff context is understood.
- [ ] Permission mode is known before file, git, GitHub, deployment, or external-system actions.
- [ ] Correct lead role is involved for the decision type.
- [ ] Deeper MDP skill is loaded when the task crosses that protocol area.
- [ ] Meaningful changes include verification and rollback evidence.
- [ ] Kanban or handover state is updated when work changes status.
