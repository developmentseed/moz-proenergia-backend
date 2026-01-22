#!/bin/bash
set -e

# ProEnergia Deployment Wrapper Script
# This script handles user context switching for proper deployment permissions
# Install to: /usr/local/bin/deploy-proenergia

SCRIPT_NAME="ProEnergia Deployment"
APP_DIR="/var/www/proenergia/app"
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

# Function to run commands as proenergia user
run_as_proenergia() {
    sudo -u proenergia -H bash -c "$1"
}

# Step 1: Git operations as proenergia user
echo -e "${YELLOW}Step 1: Pulling latest code...${NC}"
run_as_proenergia "cd $APP_DIR && git fetch origin && git pull origin main" || error_exit "Git pull failed"
log "Code updated successfully"

# Step 2: Python environment operations as proenergia user
echo -e "${YELLOW}Step 2: Updating Python dependencies...${NC}"
run_as_proenergia "cd $APP_DIR && source venv/bin/activate && pip install -r requirements.txt --upgrade" || error_exit "Pip install failed"
log "Dependencies updated"

# Step 3: Django operations as proenergia user
echo -e "${YELLOW}Step 3: Running Django migrations...${NC}"
run_as_proenergia "cd $APP_DIR && source venv/bin/activate && python manage.py migrate" || error_exit "Migration failed"
log "Migrations completed"

echo -e "${YELLOW}Step 4: Collecting static files...${NC}"
run_as_proenergia "cd $APP_DIR && source venv/bin/activate && python manage.py collectstatic --noinput" || error_exit "Collectstatic failed"
log "Static files collected"

# Step 5: Service operations as root
echo -e "${YELLOW}Step 5: Restarting application service...${NC}"
systemctl restart proenergia || error_exit "Service restart failed"
log "Service restarted"

# Step 6: Health check
echo -e "${YELLOW}Step 6: Running health check...${NC}"
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
run_as_proenergia "cd $APP_DIR && git log --oneline -5"

log "=== $SCRIPT_NAME completed successfully ==="
echo -e "\n${GREEN}=== Deployment complete ===${NC}"