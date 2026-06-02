---
name: mdp-error-observability
description: Use when designing, modifying, debugging, or operating MDP scripts, automations, cron jobs, tools, workers, or workflows that can fail.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [mdp, errors, observability, diagnostics, reliability]
    related_skills: [mdp-verification-rollback, mdp-kanban-health, systematic-debugging]
---

# MDP Error Handling and Observability

## Overview

MDP work must make failures easy to identify, understand, and recover from. Silent failure is a project risk. Good diagnostics preserve momentum because the next agent can see what failed and what to do next.

Use this skill when building or operating anything that can fail: scripts, cron jobs, workflows, modules, workers, integrations, or agent processes.

## When to Use

Use this skill when:

- Writing or changing scripts, tools, workers, cron jobs, or automations.
- Handling provider, API, auth, quota, filesystem, network, or subprocess errors.
- Designing structured status output for agents.
- A task failed and needs triage.
- A project health monitor needs signals.
- Reporting blocked or partial work.

## Required Practices

1. Catch expected errors at the correct boundary.
2. Preserve original error messages and stack traces where useful.
3. Add context: operation, path, task ID, provider, request type, or external service.
4. Avoid broad silent catches.
5. Fail fast when continuing could corrupt state or hide the problem.
6. Retry only likely transient failures.
7. Use bounded retries with backoff.
8. Log important state transitions and failure points.
9. Return structured failure information when another agent consumes the output.
10. Include recovery or escalation guidance where possible.

## Minimum Error Report Shape

Use this structure for meaningful failures:

- operation:
- component:
- input or target:
- error type:
- error message:
- stack trace or source location, if available:
- likely cause:
- retry attempted:
- current state:
- recommended next action:
- whether Human Owner input is required:

## Structured Worker Status

For automation or worker output, prefer:

```json
{
  "status": "ok|warning|blocked|failed|partial",
  "operation": "...",
  "evidence": ["..."],
  "errors": [],
  "next_action": "...",
  "requires_human": false
}
```

## Bad Patterns

Avoid:

- Catching every exception and continuing without logging.
- Replacing real errors with vague messages.
- Retrying forever.
- Swallowing auth, provider, or token errors.
- Creating partial output without marking it partial.
- Hiding failed verification.
- Reporting success when warnings or skipped steps matter.

## Common Pitfalls

1. **Logging without context.** An error message alone often isn’t enough.
2. **Retrying non-transient failures.** Auth, missing files, bad config, and validation failures usually need fixes, not retries.
3. **Failing silently in cron jobs.** Watchdogs need non-zero exits or structured alerts when broken.
4. **Treating warnings as success.** Partial success must be labeled.
5. **Skipping root-cause debugging.** Use systematic debugging before random fixes.

## Verification Checklist

- [ ] Expected errors have handling at the right boundary.
- [ ] Failures include operation, target, cause, state, and next action.
- [ ] Retries are bounded and only for transient cases.
- [ ] Automation outputs structured status when consumed by agents.
- [ ] Health monitoring can detect repeated or silent failures.
