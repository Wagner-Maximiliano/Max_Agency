#!/usr/bin/env bash
# orchestrator-tick-runner.sh — what the systemd orchestrator timer actually runs.
#
# API-budget design: the deterministic mechanics script runs EVERY tick (it only
# touches the GitHub API, not the LLM call budget). The expensive Hermes LLM is
# spawned ONLY when there is a kickoff issue to expand. Idle ticks therefore cost
# zero LLM calls — previously the LLM was spawned every tick and burned 4–10
# OpenRouter calls per idle tick (often hitting its iteration cap on a no-op).
#
# Invoked as: bash orchestrator-tick-runner.sh
# Requires (from systemd EnvironmentFile=~/.hermes/.env): PROJECT_REPO, API keys,
# TELEGRAM_* (for mechanics escalations).

set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"

L="$HOME/.hermes/profiles/orchestrator/cron-output.log"
CACHE="$HOME/.hermes-cache/Max_Agency"

echo "=== TICK $(date -Iseconds) ===" >> "$L"

# Deterministic queue management (heartbeat, promote, dispatch, reclaim, close
# merged, create CTO reviews, route verdicts, escalate). GitHub API only.
OUT=$(bash "$CACHE/hermes-config/orchestrator-mechanics.sh" 2>>"$L")
echo "$OUT" >> "$L"

# Spin up the LLM only if there are kickoff issues to turn into child tasks.
KICK=$(printf '%s' "$OUT" | python3 -c 'import json,sys
try: print(int(json.load(sys.stdin).get("kickoffs",0)))
except Exception: print(0)' 2>/dev/null || echo 0)

if [ "${KICK:-0}" -gt 0 ] 2>/dev/null; then
  echo "$(date -Iseconds) | kickoffs=$KICK -> invoking orchestrator LLM" >> "$L"
  hermes -p orchestrator chat \
    -q "$(cat "$CACHE/hermes-config/poll-prompts/orchestrator-tick.md")" \
    -Q --accept-hooks --yolo --max-turns 10 2>&1 | tail -5 >> "$L"
else
  echo "$(date -Iseconds) | TICK_OK | mechanics-only (kickoffs:0, LLM skipped)" >> "$L"
fi
