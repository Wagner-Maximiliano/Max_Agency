# Hermes Cron Jobs

Exact commands to register the polling jobs for each profile. Run by bootstrap prompt **H2** in `Human_Runbook.md`. The human normally does not run these by hand.

Cron expression `* * * * *` = every minute. Adjust if you want less frequent polling.

## Orchestrator — polls every minute

```
hermes -p orchestrator cron add \
  --name "max-agency-orchestrator-tick" \
  --schedule "* * * * *" \
  --prompt-file "$MAX_AGENCY_CACHE/hermes-config/poll-prompts/orchestrator-tick.md" \
  --env "AGENCY_REPO=$AGENCY_REPO" \
  --env "TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN" \
  --env "TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID" \
  --timeout 300
```

## Coder — polls every minute

```
hermes -p coder cron add \
  --name "max-agency-coder-tick" \
  --schedule "* * * * *" \
  --prompt-file "$MAX_AGENCY_CACHE/hermes-config/poll-prompts/coder-tick.md" \
  --env "AGENCY_REPO=$AGENCY_REPO" \
  --timeout 1500
```

## Environment variables expected

| Var | Purpose |
|---|---|
| `MAX_AGENCY_CACHE` | Local path to the cloned public repo (default: `~/.hermes-cache/Max_Agency`) |
| `AGENCY_REPO` | The project repo to operate on, e.g. `Wagner-Maximiliano/my-project` |
| `TELEGRAM_BOT_TOKEN` | Optional; for Orchestrator escalations |
| `TELEGRAM_CHAT_ID` | Optional; for Orchestrator escalations |

These should be exported in the same shell that runs H2, or persisted via `hermes env set` per profile.

## Inspecting / removing

```
hermes -p orchestrator cron list
hermes -p orchestrator cron remove max-agency-orchestrator-tick
hermes -p coder cron list
hermes -p coder cron remove max-agency-coder-tick
```

## Notes

- The `--prompt-file` flag is shown as the conventional way to feed a long prompt to a cron tick. If your Hermes version expects `--prompt` with inline text, the bootstrap prompt H2 reads the file and inlines it instead.
- `--timeout` is in seconds. Orchestrator ticks are short (5 min cap). Coder ticks may take up to 25 min (one full implementation cycle).
