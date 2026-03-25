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
    python3-pip \
    gettext

# Install PostgreSQL 16 and PostGIS
sudo apt install -y \
    postgresql-16 \
    postgresql-16-postgis-3 \
    postgresql-contrib \
    libpq-dev

# Install RabbitMQ
sudo apt install -y rabbitmq-server

# Install nginx
sudo apt install -y nginx

# Install certbot for SSL
sudo apt install -y certbot python3-certbot-nginx

# Install tippecanoe and GDAL
sudo apt install -y tippecanoe gdal-bin

# Start and enable PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Start and enable nginx
sudo systemctl start nginx
sudo systemctl enable nginx

# Start and enable RabbitMQ
sudo systemctl start rabbitmq-server
sudo systemctl enable rabbitmq-server

echo "=== Creating application user ==="

# Create app user
sudo useradd -m -s /bin/bash proenergia
sudo usermod -aG sudo proenergia

# Create application directories
sudo mkdir -p /var/www/proenergia
sudo mkdir -p /var/log/proenergia
sudo chown -R proenergia:proenergia /var/www/proenergia
sudo chown -R proenergia:proenergia /var/log/proenergia

# Create deployment log with proper permissions
sudo touch /var/log/proenergia/deployment.log
sudo chmod 666 /var/log/proenergia/deployment.log

echo "=== System setup complete ==="
echo "Next steps:"
echo "1. Run ./01_setup_infrastructure.sh to set up PostgreSQL, RabbitMQ, and generate .env"
echo "2. Run ./02_setup_application.sh as the proenergia user"
echo "3. Run ./03_setup_services.sh to configure and start services"
