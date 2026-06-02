---
name: mdp-model-cost-governance
description: Use when choosing models, providers, subagents, or automation paths for MDP work while controlling cost, quality, and token usage.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [mdp, models, cost, routing, tokens]
    related_skills: [mdp-agent-routing, mdp-context-budget, mdp-decision-gates]
---

# MDP Model and Cost Governance

## Overview

MDP uses the cheapest reliable execution path that still protects quality. Scripts handle deterministic repeatable logic. Cheap or free models handle bounded support. Premium models are reserved for hard reasoning, architecture, security, production readiness, and important decisions.

This skill prevents silent cost creep and keeps multi-agent work sustainable.

## When to Use

Use this skill when:

- Choosing a model or provider for an MDP task.
- Spawning or briefing subagents.
- Deciding whether a task should be scripted instead of model-driven.
- Reviewing model cost, provider risk, token usage, or routing quality.
- A workflow might silently fall back to paid models.
- A task needs high-end reasoning and must justify the cost.

## Routing Principles

1. Use scripts for deterministic checks, parsing, validation, polling, formatting, and repeated status reports.
2. Use cheap/free models for bounded scans, summaries, classification, inventory, and first-pass triage.
3. Use technical lead models for architecture, code review, security-sensitive changes, deployment, and production readiness.
4. Use strategic lead models for major operational, strategic, financial, or reputation decisions.
5. Never silently route to paid OpenRouter models.
6. Prefer free OpenRouter models only when their names end in `:free`.
7. Stop and report when the safe cheap route is unavailable instead of quietly using an expensive fallback.

## Cost-Aware Task Split

Before using a model, ask:

- Can a script do this exactly?
- Can a cheap worker summarize or inventory first?
- Does this need judgment, synthesis, or risk review?
- Does the result affect production, money, security, reputation, or Max directly?
- What is the smallest context that can solve it?

## Suggested Execution Lanes

- Deterministic logic: local scripts, tests, validators, parsers, cron scripts.
- Low-risk support: free model subagents with narrow prompts.
- Technical decisions: Alex lane.
- Major operational decisions: Felipe lane.
- Financial tradeoffs: Tom lane.
- Final synthesis for Max: Tony.

## Required Cost Signals

For meaningful multi-agent work, capture:

- Which model/provider lane was used.
- Why that lane was enough.
- Whether any paid path was used.
- Whether the task could be scripted next time.
- Confidence and remaining uncertainty.

## Common Pitfalls

1. **Using an LLM for deterministic work.** If a script can parse or validate it, script it.
2. **Dumping large context into workers.** Send paths and focused excerpts instead.
3. **Silent paid fallback.** If a free route fails, stop or ask before using paid capacity unless already authorized.
4. **Overusing premium models.** Save them for judgment-heavy or high-risk work.
5. **Underpowering critical reviews.** Security, architecture, deployment, and financial decisions may need stronger review.
6. **Forgetting provider failures.** Treat auth, quota, and provider errors as operational signals.

## Verification Checklist

- [ ] Deterministic parts were scripted where practical.
- [ ] Free or cheap workers were used only for low-risk bounded work.
- [ ] High-end models were reserved for justified hard reasoning or high-risk review.
- [ ] No paid OpenRouter fallback happened silently.
- [ ] Final report states the execution lane and any cost or provider risk.
