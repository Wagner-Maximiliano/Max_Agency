#!/usr/bin/env bash
# deploy.sh — sync the repo's hermes coder profile to the live WSL installation.
#
# As of Phase 2F the old polling system is retired: the WSL hermes *tick* timers/services
# and the orchestrator-mechanics script are gone, and the gate (a single Windows Scheduled
# Task) is the only scheduled job. The one piece the gate still depends on in WSL is the
# **coder profile** — the gate's coder harness invokes `hermes -p coder`, which reads
# ~/.hermes/profiles/coder/config.yaml (model.default = the benchmarked coder model).
#
# Run this after a git pull when the coder profile changed:  bash hermes-config/deploy.sh
#
# (The hermes *gateway* service — hermes-gateway.service — is managed separately and is NOT
# touched here. PROJECT_REPO / OPENROUTER_API_KEY live in ~/.hermes/.env, also not touched.)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"

log() { echo "[deploy] $*"; }

# ── Coder profile config (the only profile the gate uses) ────────────────────
src="$SCRIPT_DIR/profiles/coder/config.yaml"
dst="$HERMES_HOME/profiles/coder/config.yaml"
if [[ -f "$src" ]]; then
  mkdir -p "$(dirname "$dst")"
  cp "$src" "$dst"
  log "synced profiles/coder/config.yaml"
else
  log "WARNING: $src not found — coder profile not synced"
fi

log "deploy complete (coder profile only; the gate is the single scheduler — see scripts/register-gate-task.ps1)"
