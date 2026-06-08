#!/usr/bin/env bash
# deploy.sh — sync repo configs to live WSL installation
#
# Run this after any git pull on Max_Agency to apply config changes.
# Usage: bash hermes-config/deploy.sh
#
# What it does:
#   1. Copies profile configs to ~/.hermes/profiles/
#   2. Copies service files to ~/.config/systemd/user/
#   3. Reloads systemd

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
SYSTEMD_DIR="${SYSTEMD_DIR:-$HOME/.config/systemd/user}"

log() { echo "[deploy] $*"; }

# ── Profile configs ──────────────────────────────────────────────────────────
for profile in orchestrator coder; do
  src="$SCRIPT_DIR/profiles/$profile/config.yaml"
  dst="$HERMES_HOME/profiles/$profile/config.yaml"
  if [[ -f "$src" ]]; then
    mkdir -p "$(dirname "$dst")"
    cp "$src" "$dst"
    log "copied profiles/$profile/config.yaml"
  fi
done

# ── Service files ────────────────────────────────────────────────────────────
for svc in hermes-orchestrator-tick hermes-coder-tick; do
  src="$SCRIPT_DIR/${svc}.service"
  dst="$SYSTEMD_DIR/${svc}.service"
  if [[ -f "$src" ]]; then
    # Preserve the machine-specific Environment= line (PATH) if present
    env_line=$(grep "^Environment=" "$dst" 2>/dev/null || true)
    cp "$src" "$dst"
    if [[ -n "$env_line" ]]; then
      # Re-inject the machine-specific PATH line after EnvironmentFile=
      sed -i "/^EnvironmentFile=/a $env_line" "$dst"
    fi
    log "copied ${svc}.service"
  fi
done

# ── Orchestrator mechanics script ────────────────────────────────────────────
src="$SCRIPT_DIR/orchestrator-mechanics.sh"
dst="$HERMES_HOME/profiles/orchestrator/orchestrator-mechanics.sh"
if [[ -f "$src" ]]; then
  cp "$src" "$dst"
  chmod +x "$dst"
  log "copied orchestrator-mechanics.sh"
fi

# ── Reload systemd ───────────────────────────────────────────────────────────
systemctl --user daemon-reload
log "systemd daemon-reload done"

# Restart services if they're not currently running (oneshot — safe to restart)
for svc in hermes-orchestrator-tick hermes-coder-tick; do
  if ! systemctl --user is-active --quiet "${svc}.service" 2>/dev/null; then
    log "${svc}.service not running — no restart needed (timer will fire it)"
  fi
done

log "deploy complete"
