# Coder Profile (Hermes side)

Hermes profile that hosts the **Hermes Coder** role of the Max Agency. Model is inherited from the global Hermes config — see Human_Runbook.md § A4.

## Created by

Bootstrap prompt **H1** in `Human_Runbook.md`.

## Files installed to disk

After H1 completes:

```
~/.hermes/profiles/coder/
├── config.yaml      # from hermes-config/profiles/coder/config.yaml
├── SOUL.md          # from hermes-config/profiles/coder/SOUL.md
├── skills/          # filtered subset of public repo's /skills/, per skills.txt
├── sessions/
└── memories/
```

## How to invoke manually

```
hermes -p coder chat
```

## Scheduled work

The cron job registered by H2 wakes this profile every 60 seconds, feeds it `hermes-config/poll-prompts/coder-tick.md`, runs one tick, exits.

## Updating

Same pattern as the orchestrator profile — edit the on-disk files directly or update `skills.txt` and re-run H1.
