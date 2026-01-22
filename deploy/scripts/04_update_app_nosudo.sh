#!/bin/bash
set -e

echo "=== Updating ProEnergia application ==="

APP_DIR="/var/www/proenergia/app"

# Check if running as proenergia user
if [[ $(whoami) != "proenergia" ]]; then
   echo "This script should be run as the proenergia user"
   echo "Run: sudo -u proenergia $0"
   exit 1
fi

cd $APP_DIR

echo "Pulling latest code..."
git fetch origin
git pull origin main

echo "Activating virtual environment..."
source venv/bin/activate

echo "Checking for requirements changes..."
pip install -r requirements.txt --upgrade

echo "Running database migrations..."
python manage.py migrate

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "=== Application update complete ==="
echo ""
echo "NOTE: This version does not restart the service."
echo "To restart the service, run one of these commands:"
echo "  - As ubuntu user: sudo systemctl restart proenergia"
echo "  - Using wrapper: sudo /usr/local/bin/deploy-proenergia"
echo ""
echo "To check service status:"
echo "  systemctl status proenergia"