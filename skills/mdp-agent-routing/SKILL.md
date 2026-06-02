---
name: mdp-agent-routing
description: Use when mapping MDP roles to agents, routing work between Tony, Felipe, Alex, Tom, Silva, and specialist workers, or deciding who owns a task.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [mdp, roles, routing, delegation, governance]
    related_skills: [mdp-core, mdp-decision-gates, mdp-kanban-health]
---

# MDP Agent Routing

## Overview

MDP is role-first. Specific agents are mapped into roles, but the operating system should not depend on one hardcoded agent name. Use this skill to route work to the correct role, keep agents in their lanes, and preserve Max as final authority.

The goal is simple: the right role handles the right decision at the right cost, with clear ownership and no confusion.

## When to Use

Use this skill when:

- Starting or importing an MDP-managed project.
- Assigning work to Tony, Felipe, Alex, Tom, Silva, or specialist workers.
- Deciding whether a task needs COO, CTO, CFO, or Human Owner review.
- Writing task prompts for subagents or specialist workers.
- A project is drifting because ownership is unclear.
- You need to explain who did what and who owns the next move.

Do not use this skill as a substitute for `mdp-decision-gates` when the issue is approval, risk, or escalation.

## Role Map

- Human Owner: Max. Final authority. Can override every role.
- PA / Orchestrator: Tony. Intake, routing, momentum, synthesis, handovers, and communication.
- COO / Decision Coordinator: Felipe. Major operational, strategic, reputation, priority, and cross-agent decisions.
- CTO / Technical Lead: Alex. Architecture, engineering quality, infrastructure, automation, security, deployment, and technical review.
- CFO / Finance Lead: Tom. Budgets, pricing, subscriptions, model costs, investments, and financial tradeoffs.
- Operator / Utility Agent: Silva. Bounded low-risk scans, summaries, cleanup, formatting, inventory, and repetitive support.
- Specialist Workers: Scoped execution under a lead role. They need boundaries, expected output, evidence, and verification requirements.

## Routing Rules

1. Start with Tony for intake unless Max explicitly addresses another role.
2. Send technical architecture, implementation strategy, infrastructure, deployment, automation, or security decisions to Alex.
3. Send major operational, strategic, reputation, priority, cross-agent, or life-impact decisions to Felipe.
4. Send budgets, pricing, subscriptions, investments, provider spend, and financial tradeoffs to Tom.
5. Send bounded low-risk support work to Silva or cheap/free utility workers.
6. Send implementation-heavy scoped coding work through the technical lane, normally Alex first.
7. Keep Max as final authority for big decisions and explicit approvals.

## Delegation Prompt Shape

When routing work, include:

- Role and purpose.
- Exact task objective.
- Scope boundaries.
- Files, repos, boards, or systems involved.
- Permission mode and forbidden actions.
- Expected output format.
- Verification required.
- Risk and escalation rules.
- Whether a confidence score is required.

## Who-Did-What Reporting

For meaningful work, report:

- Owner role.
- Worker or subagent used, if any.
- Files or systems touched.
- Verification performed.
- Current confidence.
- Remaining risks.
- Next owner.

## Common Pitfalls

1. **Hardcoding agent names into the framework.** Keep MDP role-first. Map names per environment.
2. **Letting Tony make major strategic decisions alone.** Felipe is the default gate for major operational and strategic calls.
3. **Letting implementation workers own architecture.** Workers can recommend. Alex owns technical direction.
4. **Hiding delegation.** Max should be able to see which role did what.
5. **Using expensive models for bounded utility work.** Route scans and summaries to cheap/free workers when safe.
6. **Over-escalating tiny tasks.** Use the smallest competent role that can move safely.

## Verification Checklist

- [ ] The task has a clear owner role.
- [ ] Specialist workers received scope, boundaries, and expected output.
- [ ] Major decisions were routed through the correct lead.
- [ ] Max approval is requested only when needed by risk, confidence, or hard gates.
- [ ] The final summary names the owner, verification, risks, and next action.
