#!/bin/bash
set -e

echo "=== Updating ProEnergia frontend ==="

FRONTEND_DIR="/var/www/proenergia/frontend"

# Check if running as proenergia user
if [[ $(whoami) != "proenergia" ]]; then
   echo "This script should be run as the proenergia user"
   echo "Run: sudo -u proenergia $0"
   exit 1
fi

cd $FRONTEND_DIR

echo "Pulling latest code..."
git fetch origin
git reset --hard origin/main

echo "Installing dependencies..."
pnpm install

echo "Building frontend..."
pnpm run build-prod

echo "=== Frontend update complete ==="
