#!/bin/bash
set -e

# This script should be run as the proenergia user
if [[ $EUID -eq 0 ]]; then
   echo "This script should be run as the proenergia user, not root"
   exit 1
fi

echo "=== Setting up Python application ==="

APP_DIR="/var/www/proenergia"
REPO_URL="git@github.com:developmentseed/moz-proenergia-backend.git"

cd $APP_DIR

# Clone the repository if it doesn't exist
if [ ! -d "app" ]; then
    echo "Cloning repository..."
    git clone $REPO_URL app
else
    echo "Repository already exists, pulling latest changes..."
    cd app
    git pull
    cd ..
fi

cd app

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Copy environment file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating environment file from template..."
    cp ../deploy/.env.production .env
    echo "IMPORTANT: Edit .env file with your actual values!"
fi

# Run database migrations
echo "Running database migrations..."
python manage.py migrate

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Create superuser (optional)
echo "To create a superuser, run:"
echo "python manage.py createsuperuser"

echo "=== Application setup complete ==="
echo "Make sure to:"
echo "1. Update .env file with correct values"
echo "2. Run migrations again if needed"
echo "3. Run 03_setup_services.sh as root to configure services"
