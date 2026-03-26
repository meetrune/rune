#!/usr/bin/env bash
# ──────────────────────────────────────────────────
# Rune graceful shutdown hook
#
# Called by the Witty Pi 4 daemon when it detects
# input voltage drop (ignition off). Stops the Rune
# backend cleanly before the Pi shuts down.
#
# The Witty Pi 4 gives us a configurable window
# (default ~30s) before cutting power. We need to:
#   1. Stop the Rune service (flushes DB buffer)
#   2. Checkpoint the SQLite WAL
#   3. Sync filesystems
#   4. Let the Pi shut down normally
#
# Install: copy to /opt/rune/shutdown.sh
# Witty Pi config: set this as the shutdown command
# ──────────────────────────────────────────────────
set -euo pipefail

LOG_TAG="rune-shutdown"

log() {
    logger -t "$LOG_TAG" "$1"
    echo "[$(date '+%H:%M:%S')] $1"
}

log "Ignition off detected. Starting graceful shutdown..."

# 1. Stop the Rune service (this triggers the producer loop's
#    CancelledError handler, which flushes the reading buffer to DB)
if systemctl is-active --quiet rune; then
    log "Stopping Rune service..."
    # systemd handles SIGTERM -> wait -> SIGKILL via TimeoutStopSec=10 in rune.service
    systemctl stop rune
    log "Rune service stopped"
fi

# 2. Force a WAL checkpoint (merge WAL back into main DB)
#    This ensures no data is stuck in the WAL file
DB_PATH="/var/lib/rune/rune.db"
if [[ -f "$DB_PATH" ]]; then
    log "Checkpointing SQLite WAL..."
    sqlite3 "$DB_PATH" "PRAGMA wal_checkpoint(TRUNCATE);" 2>/dev/null || true
    log "WAL checkpoint complete"
fi

# 3. Sync all filesystems
log "Syncing filesystems..."
sync

log "Shutdown preparation complete. Pi will power off now."

# 4. Initiate system shutdown (Witty Pi may also do this,
#    but calling it explicitly ensures clean poweroff)
shutdown -h now
