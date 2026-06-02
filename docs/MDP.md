# MDP Project Pointer

This project is managed under MDP: Massive Development Plan.

## Project status

- Status: live
- Human Owner: Max
- Project: Game_Automation
- Repository path: `/mnt/c/Users/lobster/Github_Projects/Game_Automation`
- Default branch observed: `master`
- Project size tier: Large
- Current board: `docs/KANBAN.md`
- Current technical handoff source: `CLAUDE.md`

## Purpose of MDP here

Use MDP to improve multi-agent coordination, execution flow, continuity, and safe autonomy across several tools being built in parallel.

## Permission mode

- Mode 1 by default for MDP governance work: local file edits allowed, no commits, no pushes, no PRs, and no GitHub actions unless Max explicitly approves.
- Offline and controlled local testing are allowed when they do not touch live systems.
- Live server interaction, live website testing, or any action that affects shared live systems requires Max approval first.

## Role map

- Human Owner: Max
- PA / Orchestrator: Tony
- COO / Decision Coordinator: Felipe
- CTO / Technical Lead: Alex
- CFO / Financial Review: Tom
- Operator / Utility Agent: Silva

## Always-read rule

Before working in this repo:

1. Read this file first.
2. Read `CLAUDE.md` for current technical state.
3. Read `docs/KANBAN.md` for active work.
4. Read `docs/reviews/GATE_REVIEW_TIER2.md` for autonomy boundaries.
5. Load relevant MDP skills on demand.

## Recommended MDP skill routing

- `mdp-core`
- `mdp-project-kickoff`
- `mdp-kanban-health`
- `mdp-handover-restart`
- `mdp-verification-rollback`
- `mdp-file-safety`
- `mdp-repo-permission-modes`

## Current operating picture

- Repo already has significant project structure, tests, docs, and handoffs.
- Multiple workstreams exist in parallel: `vhid`, `apps/macro_bot`, `apps/trainer`, `apps/packet_lab`, dashboard tooling, and live-validation docs.
- Existing governance artifacts already describe autonomy boundaries, but MDP pointer and standard handover package were missing.
- Working tree is currently dirty, so new MDP adoption should not assume a clean baseline.

## Safety rules

- Do not touch GitHub unless Max explicitly approves.
- Do not commit or merge unless Max explicitly approves.
- Do not interact with live Euro-PvP systems without Max approval.
- Do not silently overwrite files.
- Prefer narrow patches over full-file replacements.
- Keep evidence, validation notes, and rollback notes for meaningful changes.

## Immediate next focus

1. Establish MDP continuity artifacts.
2. Align the current Kanban board with MDP routing and workstream visibility.
3. Identify the first few safe parallel tasks that can proceed offline.
4. Escalate only true decisions, approvals, or live-system gates.
