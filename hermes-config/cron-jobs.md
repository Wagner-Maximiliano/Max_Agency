# Hermes Cron Jobs

Exact commands to register the polling jobs for each profile. **H2 runs these automatically** — the human normally does not run them by hand.

`* * * * *` = every minute. Use `*/5 * * * *` for every 5 minutes if you want to reduce rate.

## Actual hermes cron syntax

```
hermes cron add SCHEDULE PROMPT_TEXT --name NAME --profile PROFILE
```

- `schedule` and `prompt` are **positional** (not flags)
- No `--env`, `--prompt-file`, or `--timeout` flags exist
- `PROJECT_REPO` is stored in `~/.hermes/.env` so all hermes processes can read it

## Orchestrator — registers via H2

```bash
hermes cron add '* * * * *' "$(cat ~/.hermes-cache/Max_Agency/hermes-config/poll-prompts/orchestrator-tick.md)" \
  --name "max-agency-orchestrator-tick" \
  --profile orchestrator
```

## Coder — registers via H2

```bash
hermes cron add '* * * * *' "$(cat ~/.hermes-cache/Max_Agency/hermes-config/poll-prompts/coder-tick.md)" \
  --name "max-agency-coder-tick" \
  --profile coder
```

## PROJECT_REPO env var

H2 writes `PROJECT_REPO=<value>` to `~/.hermes/.env`. Hermes loads this file at startup, making it available to all cron ticks.

To update for a new project: re-run H2 with the new repo slug.

## Inspecting / removing

```bash
# List jobs per profile
hermes -p orchestrator cron list
hermes -p coder cron list

# Remove by job ID (hex from cron list output)
hermes cron remove <job_id>
```

## Notes

- H2 handles "remove if already exists" automatically before re-adding.
- The `--profile` flag on `cron add` is different from `hermes -p PROFILE cron list`. Both work correctly.
- Telegram vars (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_HOME_CHANNEL`) are already in `~/.hermes/.env` from Hermes setup — no extra action needed.
