# Max Agency — Baseline

Baseline scaffold for an autonomous multi-agent developers agency. Hermes hosts the non-Anthropic roles as isolated profiles (`orchestrator`, `coder`). The Claude Code Windows app hosts the Anthropic roles (Architect, CTO, Anthropic Coder) on a Windows Task Scheduler routine. GitHub is the coordination bus.

## Read this first

→ **[`Human_Runbook.md`](Human_Runbook.md)** is the only doc you need. It contains the setup steps and the copy-paste prompts to bootstrap everything.

## Layout

```
agents/                Role contracts (architect, cto, orchestrator, coder)
docs/                  Laws, Policies, Protocols, Rules (MDP, AMA, ...)
skills/                Reusable skills agents discover on demand
hermes-config/         Hermes-native profile templates, cron jobs, poll prompts
claude-code-routine/   Windows Task Scheduler routine for the Anthropic side
templates/             PLAN.md / State.md skeletons
scripts/               PowerShell helpers (state rebuild, project setup)
.github/               Issue template, PR template, CI workflow
Human_Runbook.md       The only human-facing doc
Highlevel_Plan_V2.0.md Architecture
CODING_STANDARDS.md    Code rules every agent follows
```

## Public mirror

This baseline is mirrored at **https://github.com/Wagner-Maximiliano/Max_Agency** so Hermes prompts can clone it during bootstrap.
