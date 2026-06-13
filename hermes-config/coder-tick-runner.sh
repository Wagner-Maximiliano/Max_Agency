#!/usr/bin/env bash
# coder-tick-runner.sh — what the systemd coder timer actually runs.
#
# API-budget design: a cheap GitHub-API pre-check decides whether there is any
# claimable work BEFORE spawning the Hermes LLM. The coder only ever acts on
# unclaimed `in-progress` + `assigned:hermes-coder` + `role:coder` issues
# (see poll-prompts/coder-tick.md step 2), so we gate on exactly that. Idle ticks
# cost zero LLM calls — previously the LLM was spawned every tick and could burn
# its entire 30-call budget looping on a no-op.
#
# Invoked as: bash coder-tick-runner.sh
# Requires (from systemd EnvironmentFile=~/.hermes/.env): PROJECT_REPO, API keys.

set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"

L="$HOME/.hermes/profiles/coder/cron-output.log"
CACHE="$HOME/.hermes-cache/Max_Agency"
REPO="${PROJECT_REPO:-}"

echo "=== TICK $(date -Iseconds) ===" >> "$L"

if [ -z "$REPO" ]; then
  echo "$(date -Iseconds) | NO_REPO (PROJECT_REPO unset)" >> "$L"
  exit 0
fi

# Cheap pre-check: count UNCLAIMED issues this coder would actually pick up.
CLAIMABLE=$(gh issue list --repo "$REPO" \
  --label in-progress --label assigned:hermes-coder --label role:coder \
  --state open --json number,assignees \
  --jq '[.[] | select(.assignees | length == 0)] | length' 2>>"$L" || echo 0)

if [ "${CLAIMABLE:-0}" -gt 0 ] 2>/dev/null; then
  echo "$(date -Iseconds) | $CLAIMABLE claimable -> invoking coder LLM" >> "$L"
  hermes -p coder chat \
    -q "$(cat "$CACHE/hermes-config/poll-prompts/coder-tick.md")" \
    -Q --accept-hooks --yolo --max-turns 30 2>&1 | tail -1 >> "$L"
else
  echo "$(date -Iseconds) | NO_WORK | no unclaimed in-progress assigned:hermes-coder issues (LLM skipped)" >> "$L"
fi
