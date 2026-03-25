#!/bin/bash
set -e

# This script should be run as the proenergia user
if [[ $EUID -eq 0 ]]; then
   echo "This script should be run as the proenergia user, not root"
   exit 1
fi

echo "=== Setting up Python application ==="

APP_DIR="/var/www/proenergia"
REPO_URL="https://github.com/developmentseed/moz-proenergia-backend.git"

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

# Check if environment file exists (should be created by 01_setup_infrastructure.sh)
if [ ! -f ".env" ]; then
    echo "ERROR: .env file not found!"
    echo "Please run 01_setup_infrastructure.sh first to generate the .env file."
    exit 1
fi

echo "Using existing .env file"

# Run database migrations
echo "Running database migrations..."
python manage.py migrate

# Create cache table for database cache backend
echo "Creating cache table..."
python manage.py createcachetable

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Compile translation messages
echo "Compiling translation files..."
python manage.py compilemessages -f || echo "Translation compilation skipped (no messages found)"

# Create superuser (optional)
echo ""
echo "=== Application setup complete ==="
echo ""
echo "To create a Django admin superuser, run:"
echo "  cd $APP_DIR/app"
echo "  source venv/bin/activate"
echo "  python manage.py createsuperuser"
echo ""
echo "Next step: Run ./03_setup_services.sh as root to configure and start services"
