# Hermes Timers

> **Note:** The real runtime is **systemd user timers**, not Hermes built-in cron. Profile-cron jobs registered by H2 are not auto-run by the Hermes gateway on this setup — the systemd timers (`hermes-orchestrator-tick.timer`, `hermes-coder-tick.timer`) are what actually fire the ticks every 5 minutes.

## Deploying the timers

After H3 completes (or after any agency repo update), run:

```bash
git -C ~/.hermes-cache/Max_Agency pull --rebase && \
  bash ~/.hermes-cache/Max_Agency/hermes-config/deploy.sh
```

`deploy.sh` copies the service and timer files to `~/.config/systemd/user/` and runs `systemctl --user daemon-reload`.

## Checking timer status

```bash
systemctl --user list-timers hermes-orchestrator-tick.timer hermes-coder-tick.timer
```

## Logs

```bash
tail -f ~/.hermes/profiles/orchestrator/cron-output.log
tail -f ~/.hermes/profiles/coder/cron-output.log
```

## Mechanics script (orchestrator only)

The orchestrator tick calls `orchestrator-mechanics.sh` each run — this script handles all deterministic queue operations. To run it manually for debugging:

```bash
PROJECT_REPO=owner/repo bash ~/.hermes/profiles/orchestrator/orchestrator-mechanics.sh
```

## Hermes cron commands (reference — not used in production)

H2 registers these cron jobs inside Hermes, but they are not the active runtime on this machine:

```bash
# List jobs per profile
hermes -p orchestrator cron list
hermes -p coder cron list

# Remove by job ID (hex from cron list output)
hermes cron remove <job_id>
```

`PROJECT_REPO` is stored in `~/.hermes/.env` and is read by all Hermes processes and by `orchestrator-mechanics.sh`.
