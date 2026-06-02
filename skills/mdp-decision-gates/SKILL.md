---
name: mdp-decision-gates
description: "Use when an MDP project needs confidence scoring, escalation, approval routing, blocked-project handling, or a compact decision brief."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [mdp, decisions, escalation, approvals, confidence, governance]
    related_skills: [mdp-core, mdp-project-kickoff, mdp-verification-rollback]
---

# MDP Decision Gates

## Overview

This skill governs decisions that may affect strategy, operations, technical architecture, finance, reputation, security, production, live systems, or Human Owner priorities.

The goal is not bureaucracy. The goal is momentum with safety: proceed when safe, escalate when needed, and never hide uncertainty.

## When to Use

Use this skill when:

- Confidence is below the project threshold.
- A task is blocked and no obvious safe next step exists.
- The action crosses role boundaries.
- The action affects production, live systems, money, reputation, legal, security, user data, or irreversible state.
- You need a COO, CTO, CFO, or Human Owner decision.
- You need to write a compact decision brief.

Do not use this for low-risk local work with clear scope, clear rollback, and high confidence.

## Confidence Rule

Default MDP threshold:

- **95 percent or higher:** proceed only if inside permission mode and not a reserved Human Owner gate. Inform the Human Owner when appropriate.
- **Below 95 percent:** escalate with a compact decision brief.

High confidence does not bypass hard gates. Human Owner approval may still be required for high-risk, irreversible, legal, financial, reputation, security, production, live-system, or privileged repository actions.

A project may declare a lower autonomy threshold for a specific experiment, but hard gates still stand.

## Role Routing

- COO reviews major operational, strategic, cross-agent, reputation, business, or life-impact decisions.
- CTO reviews technical architecture, engineering strategy, infrastructure, security, deployment, and production-readiness decisions.
- CFO reviews costs, budgets, pricing, subscriptions, paid APIs, investments, and financial tradeoffs.
- PA synthesizes, routes, communicates, and keeps the project moving.
- Human Owner decides when risk, ambiguity, permission mode, or impact requires it.

Cross-lane decisions need the relevant leads. Example: expensive production infrastructure needs CTO plus CFO, and likely COO or Human Owner depending on risk.

## Blocked Project Rule

Before declaring the project stalled:

1. Identify the blocker.
2. Gather deterministic facts with scripts or focused reads.
3. Look for safe parallel work.
4. Ask the relevant lead role for review if needed.
5. Escalate to the Human Owner only when no safe progress remains, confidence is below threshold, or a hard gate is crossed.

## Compact Decision Brief

Use this shape:

- Decision needed:
- Context:
- Options:
- Recommendation:
- Confidence:
- Why confidence is not higher:
- Risk if wrong:
- Rollback path:
- Safe parallel work available:
- Required approver:

## Common Pitfalls

1. Treating confidence as permission.
2. Escalating every small uncertainty instead of gathering facts first.
3. Continuing unsafe work because some parallel work exists.
4. Skipping COO/CTO/CFO review for cross-lane decisions.
5. Asking the Human Owner a vague question instead of a compact decision brief.
6. Making a decision without rollback information.

## Verification Checklist

- [ ] Confidence score is stated for meaningful decisions.
- [ ] Correct role lead is involved.
- [ ] Human Owner hard gates are respected.
- [ ] Rollback path is known or impossibility is explicit.
- [ ] Safe parallel work was considered before declaring a stall.
- [ ] Decision brief is compact and actionable when escalation is needed.
