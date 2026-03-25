#!/bin/bash
set -e

echo "=== Setting up PostgreSQL database ==="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)"
   exit 1
fi

# Function to generate secure password
generate_password() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-25
}

# Database configuration
DB_NAME="${DB_NAME:-proenergia_db}"
DB_USER="${DB_USER:-proenergia}"
DB_PASSWORD="${DB_PASSWORD:-$(generate_password)}"

echo "Database name: $DB_NAME"
echo "Database user: $DB_USER"
echo ""
echo "IMPORTANT: Save this database password securely!"
echo "Database password: $DB_PASSWORD"
echo ""

# Install PostgreSQL if not already installed
if ! command -v psql &> /dev/null; then
    echo "Installing PostgreSQL 16 and PostGIS..."
    apt update
    apt install -y \
        postgresql-16 \
        postgresql-16-postgis-3 \
        postgresql-contrib \
        libpq-dev
fi

# Start and enable PostgreSQL
systemctl start postgresql
systemctl enable postgresql

echo "=== Creating database and user ==="

# Check if user exists, create if not
sudo -u postgres psql -tAc "SELECT 1 FROM pg_user WHERE usename='$DB_USER'" | grep -q 1 || \
    sudo -u postgres createuser -s "$DB_USER"

# Set password for database user
sudo -u postgres psql -c "ALTER USER $DB_USER PASSWORD '$DB_PASSWORD';"

# Check if database exists, create if not
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
    sudo -u postgres createdb "$DB_NAME" -O "$DB_USER"

echo "=== Enabling PostgreSQL extensions ==="

# Enable required extensions
sudo -u postgres psql -d "$DB_NAME" << EOF
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
EOF

echo "=== Configuring PostgreSQL authentication ==="

# Update pg_hba.conf to use md5 authentication for local connections
PG_VERSION="16"
PG_CONFIG_DIR="/etc/postgresql/$PG_VERSION/main"

# Backup original pg_hba.conf
cp "$PG_CONFIG_DIR/pg_hba.conf" "$PG_CONFIG_DIR/pg_hba.conf.backup.$(date +%Y%m%d)"

# Ensure local connections use md5 authentication
if ! grep -q "local   $DB_NAME   $DB_USER" "$PG_CONFIG_DIR/pg_hba.conf"; then
    # Add specific rule for our database and user before the default local rule
    sed -i "/^local   all             all/i local   $DB_NAME   $DB_USER   md5" "$PG_CONFIG_DIR/pg_hba.conf"
fi

# Reload PostgreSQL configuration
systemctl reload postgresql

echo "=== Testing database connection ==="

# Test connection
PGPASSWORD="$DB_PASSWORD" psql -U "$DB_USER" -d "$DB_NAME" -h localhost -c "SELECT version();" > /dev/null 2>&1 && \
    echo "✓ Database connection successful" || \
    echo "✗ Database connection failed - please check configuration"

echo ""
echo "=== Database setup complete ==="
echo ""
echo "Database connection string for .env file:"
echo "DATABASE_URL=postgis://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME"
echo ""
echo "Please save the database password securely!"
echo "Password: $DB_PASSWORD"
echo ""
echo "Next step: Run the PostgreSQL optimization script (optional but recommended)"