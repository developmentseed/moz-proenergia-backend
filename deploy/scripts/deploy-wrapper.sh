#!/bin/bash
set -e

# ProEnergia Deployment Wrapper Script
# Handles user context switching for deployment
# Install to: /usr/local/bin/deploy-proenergia

APP_DIR="/var/www/proenergia/app"
# Try new script name first, fall back to old name for compatibility
if [ -f "$APP_DIR/deploy/scripts/05_update_app.sh" ]; then
    UPDATE_SCRIPT="$APP_DIR/deploy/scripts/05_update_app.sh"
else
    UPDATE_SCRIPT="$APP_DIR/deploy/scripts/04_update_app_nosudo.sh"
fi
LOG_FILE="/var/log/proenergia/deployment.log"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    echo "Error: This script must be run as root or with sudo"
    exit 1
fi

log "Starting deployment"

# Run update script as proenergia user
if ! sudo -u proenergia -H bash -c "$UPDATE_SCRIPT"; then
    log "ERROR: Update script failed"
    echo "Error: Update failed. Check logs: tail -f $LOG_FILE"
    exit 1
fi

log "Application updated"

# Restart services
if ! systemctl restart proenergia; then
    log "ERROR: Service restart failed"
    echo "Error: Service restart failed. Check logs: journalctl -u proenergia -f"
    exit 1
fi

# Restart Celery services if they are enabled
if systemctl is-enabled --quiet proenergia-celery 2>/dev/null; then
    systemctl restart proenergia-celery || log "WARNING: Celery worker restart failed"
fi

if systemctl is-enabled --quiet proenergia-celerybeat 2>/dev/null; then
    systemctl restart proenergia-celerybeat || log "WARNING: Celery beat restart failed"
fi

log "Services restarted"
log "Deployment completed successfully"

echo "Deployment complete"