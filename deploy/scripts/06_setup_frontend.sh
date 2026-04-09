#!/bin/bash
set -e

echo "=== Setting up ProEnergia frontend ==="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)"
   exit 1
fi

FRONTEND_DIR="/var/www/proenergia/frontend"
REPO_URL="https://github.com/developmentseed/moz-proenergia-web.git"

echo "Setting up frontend to be served at /app"

echo ""
echo "=== Step 1: Installing Node.js v24 ==="

curl -fsSL https://deb.nodesource.com/setup_24.x | bash -
apt-get install -y nodejs

echo "Node.js version: $(node --version)"

echo ""
echo "=== Step 2: Installing pnpm ==="

npm install -g pnpm
echo "pnpm version: $(pnpm --version)"

echo ""
echo "=== Step 3: Cloning frontend repository ==="

if [ -d "$FRONTEND_DIR" ]; then
    echo "Frontend directory already exists, pulling latest..."
    sudo -u proenergia bash -c "cd $FRONTEND_DIR && git fetch origin && git reset --hard origin/main"
else
    git clone "$REPO_URL" "$FRONTEND_DIR"
fi

chown -R proenergia:proenergia "$FRONTEND_DIR"

echo ""
echo "=== Step 4: Building frontend ==="

sudo -u proenergia bash -c "cd $FRONTEND_DIR && pnpm install && pnpm run build"

# Note: Nginx configuration for /app is already included in the main proenergia.conf
echo ""
echo "Frontend build complete. It will be served at /app on the main domain."

echo ""
echo "========================================================================="
echo "                     FRONTEND SETUP COMPLETE                            "
echo "========================================================================="
echo ""
echo "Your frontend should now be available at: /app on your main domain"
echo ""
echo "To update the frontend later, run as proenergia user:"
echo "  sudo -u proenergia /var/www/proenergia/app/deploy/scripts/07_update_frontend.sh"
