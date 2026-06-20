# Max Agency — Baseline

Autonomous multi-agent developers agency. **One deterministic gate** (a cheap script, the
only scheduled job) reads a GitHub board and wakes exactly one LLM per actionable issue:
orchestrator triage/expansion (Codex `gpt-5.4-mini`), coder (OpenRouter `xiaomi/mimo-v2.5`
via hermes in WSL), and architect + CTO (Claude Opus). The human interface is one label,
**`AI`**: add it to an issue to opt it in; the gate triages → plans → builds → cross-vendor
reviews → merges. GitHub is the coordination bus.

> **⚠ As of Phase 2F the old polling system is retired.** The per-model `assigned:*`
> self-selection labels, the WSL hermes *tick* timers, and the Claude Code 5-min routine are
> gone — replaced by the gate (`gate/`, see [`gate/README.md`](gate/README.md)). The single
> scheduled job is now one Windows Scheduled Task running the gate
> (`scripts/register-gate-task.ps1`). Docs below that still describe the old `assigned:*`
> flow are historical and are being trimmed in Phase 3.

## Read this first

→ **[`gate/README.md`](gate/README.md)** — the current system (the gate). The roadmap of
record is [`docs/GATE_ROADMAP.md`](docs/GATE_ROADMAP.md). `Human_Runbook.md` still documents
the retired polling flow (Phase 3 will rewrite it).

## Layout

```
agents/                              Role contracts (architect, cto, orchestrator, coder)
docs/                                Laws, Policies, Protocols, Rules (AMA, ...)
skills/                              Reusable skills agents discover on demand
gate/                                The deterministic gate — the current system (see gate/README.md)
hermes-config/                       Hermes coder profile (the gate's coder harness uses it); deploy.sh syncs it
templates/                           PLAN.md / State.md skeletons
scripts/                             PowerShell helpers (state rebuild, project setup)
.github/                             Issue template, PR template, CI workflow
Human_Runbook.md                     The only human-facing doc — setup, operation, troubleshooting
Highlevel_Plan_V2.0.md               Canonical architecture reference
CODING_STANDARDS.md                  Code rules every agent follows
max-agency-flow-diagram.html         Visual explainer — how the system works
max-agency-flow-diagram(Production).html  Visual quick-start — install steps + how it works
```

## Public mirror

This baseline is mirrored at **https://github.com/Wagner-Maximiliano/Max_Agency** so Hermes prompts can clone it during bootstrap.

## License

No LICENSE file is present yet — **all rights reserved until one is added**. This means you can read and fork the code for personal study, but cannot legally redistribute or use it in production without explicit permission. A license will be chosen and added in a future update.
