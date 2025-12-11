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
python manage.py migrate --settings=proenergia.config.production

echo "Collecting static files..."
python manage.py collectstatic --noinput --settings=proenergia.config.production

echo "Restarting application service..."
sudo systemctl restart proenergia

echo "Waiting for service to start..."
sleep 5

echo "Checking service status..."
if systemctl is-active --quiet proenergia; then
    echo "✓ Service is running"
else
    echo "✗ Service failed to start"
    echo "Check logs: sudo journalctl -u proenergia -f"
    exit 1
fi

echo "Running basic health check..."
if curl -f -s http://localhost:8000/admin/ > /dev/null; then
    echo "✓ Application is responding"
else
    echo "⚠ Application may not be responding correctly"
    echo "Check logs: sudo journalctl -u proenergia -f"
fi

echo "=== Update complete ==="