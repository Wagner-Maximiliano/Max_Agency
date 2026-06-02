# Orchestrator Profile

Hermes profile that hosts the **Orchestrator** role of the Max Agency.

## Created by

Bootstrap prompt **H1** in `Human_Runbook.md`.

## Files installed to disk

After H1 completes, the following exist:

```
~/.hermes/profiles/orchestrator/
├── config.yaml      # from hermes-config/profiles/orchestrator/config.yaml
├── SOUL.md          # from hermes-config/profiles/orchestrator/SOUL.md
├── skills/          # filtered subset of public repo's /skills/, per skills.txt
├── sessions/        # created by Hermes on first run
└── memories/        # created by Hermes on first run
```

## How to invoke manually

```
hermes -p orchestrator chat
```

## Scheduled work

The cron job registered by bootstrap **H2** wakes this profile every 60 seconds, feeds it `hermes-config/poll-prompts/orchestrator-tick.md`, runs one tick, exits.

## Updating

To change the model or toolsets: edit `~/.hermes/profiles/orchestrator/config.yaml` directly (or `orchestrator config set model.default <new-model>`).

To add new skills: add filenames to `skills.txt` in the public repo, then re-run H1.

To change the soul: edit `~/.hermes/profiles/orchestrator/SOUL.md` directly.
