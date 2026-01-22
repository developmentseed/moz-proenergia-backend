#!/bin/bash
set -e

# ProEnergia Deployment Wrapper Script
# This script handles user context switching for proper deployment permissions
# Install to: /usr/local/bin/deploy-proenergia

SCRIPT_NAME="ProEnergia Deployment"
APP_DIR="/var/www/proenergia/app"
UPDATE_SCRIPT="$APP_DIR/deploy/scripts/04_update_app_nosudo.sh"
LOG_FILE="/var/log/proenergia/deployment.log"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Error handling
error_exit() {
    echo -e "${RED}Error: $1${NC}" >&2
    log "ERROR: $1"
    exit 1
}

# Check if running as root or with sudo
if [[ $EUID -ne 0 ]]; then
    error_exit "This script must be run as root or with sudo"
fi

log "=== Starting $SCRIPT_NAME ==="

# Step 1: Run update script as proenergia user
echo -e "${YELLOW}Running application update...${NC}"
sudo -u proenergia -H bash -c "$UPDATE_SCRIPT" || error_exit "Update script failed"
log "Application updated successfully"

# Step 2: Service operations as root
echo -e "${YELLOW}Restarting application service...${NC}"
systemctl restart proenergia || error_exit "Service restart failed"
log "Service restarted"

# Step 3: Health check
echo -e "${YELLOW}Running health check...${NC}"
sleep 5

# Check if service is active
if systemctl is-active --quiet proenergia; then
    echo -e "${GREEN}✓ Service is running${NC}"
    log "Service health check passed"
else
    error_exit "Service failed to start. Check logs: journalctl -u proenergia -f"
fi

# Check HTTP response
if curl -f -s -o /dev/null -w "%{http_code}" http://localhost:8000/admin/ | grep -q "200\|301\|302"; then
    echo -e "${GREEN}✓ Application is responding${NC}"
    log "HTTP health check passed"
else
    echo -e "${YELLOW}⚠ Application may not be responding correctly${NC}"
    log "WARNING: HTTP health check failed"
    echo "Check logs: journalctl -u proenergia -f"
fi

# Show recent git commits
echo -e "\n${GREEN}Recent commits deployed:${NC}"
sudo -u proenergia -H bash -c "cd $APP_DIR && git log --oneline -5"

log "=== $SCRIPT_NAME completed successfully ==="
echo -e "\n${GREEN}=== Deployment complete ===${NC}"