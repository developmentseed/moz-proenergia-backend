#!/bin/bash
set -e

echo "=== Setting up system dependencies ==="

# Update system packages
sudo apt update
sudo apt upgrade -y

# Install basic dependencies
sudo apt install -y \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    build-essential

# Install Python 3.12 and related tools
sudo apt install -y \
    python3 \
    python3-venv \
    python3-dev \
    python3-pip

# Install PostgreSQL 16 and PostGIS
sudo apt install -y \
    postgresql-16 \
    postgresql-16-postgis-3 \
    postgresql-contrib \
    libpq-dev

# Install nginx
sudo apt install -y nginx

# Install certbot for SSL
sudo apt install -y certbot python3-certbot-nginx

# Start and enable PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Start and enable nginx
sudo systemctl start nginx
sudo systemctl enable nginx

echo "=== Creating database and user ==="

# Create database user and database
sudo -u postgres createuser -s proenergia
sudo -u postgres createdb proenergia_db -O proenergia

# Enable PostGIS extension
sudo -u postgres psql -d proenergia_db -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# Set password for database user
sudo -u postgres psql -c "ALTER USER proenergia PASSWORD 'proenergia_password';"

echo "=== Creating application user ==="

# Create app user
sudo useradd -m -s /bin/bash proenergia
sudo usermod -aG sudo proenergia

# Create application directories
sudo mkdir -p /var/www/proenergia
sudo mkdir -p /var/log/proenergia
sudo chown -R proenergia:proenergia /var/www/proenergia
sudo chown -R proenergia:proenergia /var/log/proenergia

echo "=== System setup complete ==="
echo "Next steps:"
echo "1. Run 02_setup_app.sh as the proenergia user"
echo "2. Update /var/www/proenergia/.env with your settings"
echo "3. Run 03_setup_services.sh"