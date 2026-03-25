#!/bin/bash
set -e

echo "=== Setting up Infrastructure (PostgreSQL, RabbitMQ, Environment) ==="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)"
   exit 1
fi

# Get domain parameter
DOMAIN=${1:-"localhost"}
if [ "$DOMAIN" == "localhost" ]; then
    echo "Warning: No domain specified, using localhost"
    echo "Usage: $0 your-domain.com"
    echo ""
fi

# Function to generate secure password
generate_password() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-25
}

# Function to generate Django secret key
generate_secret_key() {
    python3 -c 'import secrets; print(secrets.token_urlsafe(50))'
}

echo ""
echo "=== Step 1: PostgreSQL Setup ==="
echo ""

# Database configuration
DB_NAME="proenergia_db"
DB_USER="proenergia"
DB_PASSWORD=$(generate_password)

# Check if user exists, create if not
sudo -u postgres psql -tAc "SELECT 1 FROM pg_user WHERE usename='$DB_USER'" | grep -q 1 || \
    sudo -u postgres createuser -s "$DB_USER"

# Set password for database user
sudo -u postgres psql -c "ALTER USER $DB_USER PASSWORD '$DB_PASSWORD';"

# Check if database exists, create if not
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
    sudo -u postgres createdb "$DB_NAME" -O "$DB_USER"

# Enable required extensions
echo "Enabling PostgreSQL extensions..."
sudo -u postgres psql -d "$DB_NAME" << EOF
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
EOF

# Configure PostgreSQL authentication
PG_VERSION="16"
PG_CONFIG_DIR="/etc/postgresql/$PG_VERSION/main"

# Backup original pg_hba.conf
cp "$PG_CONFIG_DIR/pg_hba.conf" "$PG_CONFIG_DIR/pg_hba.conf.backup.$(date +%Y%m%d)"

# Ensure local connections use md5 authentication for our database
if ! grep -q "local   $DB_NAME   $DB_USER" "$PG_CONFIG_DIR/pg_hba.conf"; then
    sed -i "/^local   all             all/i local   $DB_NAME   $DB_USER   md5" "$PG_CONFIG_DIR/pg_hba.conf"
fi

echo ""
echo "=== Step 2: PostgreSQL Optimization ==="
echo ""

# Get system memory in MB
TOTAL_MEM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_MEM_MB=$((TOTAL_MEM_KB / 1024))

echo "System memory: ${TOTAL_MEM_MB}MB"

PG_CONFIG_FILE="$PG_CONFIG_DIR/postgresql.conf"

# Backup original configuration
cp "$PG_CONFIG_FILE" "$PG_CONFIG_FILE.backup.$(date +%Y%m%d)"

# Function to update PostgreSQL config
update_pg_config() {
    local param=$1
    local value=$2
    
    if grep -q "^$param = " "$PG_CONFIG_FILE"; then
        sed -i "s/^$param = .*/$param = $value/" "$PG_CONFIG_FILE"
    elif grep -q "^#$param = " "$PG_CONFIG_FILE"; then
        sed -i "s/^#$param = .*/$param = $value/" "$PG_CONFIG_FILE"
    else
        echo "$param = $value" >> "$PG_CONFIG_FILE"
    fi
}

# Apply optimizations based on system memory
if [ $TOTAL_MEM_MB -ge 16384 ]; then
    SHARED_BUFFERS="4GB"
elif [ $TOTAL_MEM_MB -ge 8192 ]; then
    SHARED_BUFFERS="2GB"
elif [ $TOTAL_MEM_MB -ge 4096 ]; then
    SHARED_BUFFERS="1GB"
else
    SHARED_BUFFERS="256MB"
fi

WORK_MEM="32MB"
MAINTENANCE_WORK_MEM="512MB"
EFFECTIVE_CACHE_SIZE="$((TOTAL_MEM_MB * 3 / 4))MB"

echo "Applying PostgreSQL optimizations..."
update_pg_config "shared_buffers" "$SHARED_BUFFERS"
update_pg_config "work_mem" "$WORK_MEM"
update_pg_config "maintenance_work_mem" "$MAINTENANCE_WORK_MEM"
update_pg_config "effective_cache_size" "$EFFECTIVE_CACHE_SIZE"
update_pg_config "max_connections" "200"
update_pg_config "checkpoint_completion_target" "0.9"
update_pg_config "wal_buffers" "16MB"
update_pg_config "max_wal_size" "2GB"
update_pg_config "min_wal_size" "512MB"
update_pg_config "random_page_cost" "1.1"
update_pg_config "effective_io_concurrency" "200"
update_pg_config "default_statistics_target" "100"
update_pg_config "autovacuum" "on"
update_pg_config "autovacuum_max_workers" "4"
update_pg_config "autovacuum_vacuum_scale_factor" "0.1"
update_pg_config "autovacuum_analyze_scale_factor" "0.05"
update_pg_config "log_min_duration_statement" "1000"
update_pg_config "statement_timeout" "600000"
update_pg_config "lock_timeout" "10000"
update_pg_config "idle_in_transaction_session_timeout" "300000"

# Reload PostgreSQL configuration
systemctl reload postgresql

# Test connection
PGPASSWORD="$DB_PASSWORD" psql -U "$DB_USER" -d "$DB_NAME" -h localhost -c "SELECT version();" > /dev/null 2>&1 && \
    echo "✓ PostgreSQL configured and optimized" || \
    echo "✗ PostgreSQL configuration failed"

echo ""
echo "=== Step 3: RabbitMQ Setup ==="
echo ""

# Generate RabbitMQ password
RABBITMQ_USER="proenergia"
RABBITMQ_PASSWORD=$(generate_password)
RABBITMQ_VHOST="proenergia_vhost"

# Start RabbitMQ if not running
systemctl start rabbitmq-server
systemctl enable rabbitmq-server

# Wait for RabbitMQ to be ready
sleep 5

# Create RabbitMQ user and vhost
rabbitmqctl delete_user $RABBITMQ_USER 2>/dev/null || true
rabbitmqctl add_user $RABBITMQ_USER "$RABBITMQ_PASSWORD"
rabbitmqctl add_vhost $RABBITMQ_VHOST 2>/dev/null || true
rabbitmqctl set_permissions -p $RABBITMQ_VHOST $RABBITMQ_USER ".*" ".*" ".*"
rabbitmqctl set_user_tags $RABBITMQ_USER administrator

echo "✓ RabbitMQ configured"

echo ""
echo "=== Step 4: Creating Environment Configuration ==="
echo ""

# Generate Django secret key
DJANGO_SECRET_KEY=$(generate_secret_key)

# Create .env file
ENV_FILE="/var/www/proenergia/app/.env"

# Ensure app directory exists
mkdir -p /var/www/proenergia/app

cat > "$ENV_FILE" << EOF
# Django Configuration
DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY
DJANGO_DEBUG=False
DJANGO_SETTINGS_MODULE=proenergia.config.production

# Database Configuration
DATABASE_URL=postgis://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME

# Security
ALLOWED_HOSTS=$DOMAIN,www.$DOMAIN
CSRF_TRUSTED_ORIGINS=https://$DOMAIN,https://www.$DOMAIN

# Static and Media Files
STATIC_ROOT=/var/www/proenergia/app/staticfiles
MEDIA_ROOT=/var/www/proenergia/app/media

# Logging
DJANGO_LOG_LEVEL=INFO

# Cache Configuration
CACHE_BACKEND=django.core.cache.backends.db.DatabaseCache
CACHE_LOCATION=summaries_cache_table

# Celery/RabbitMQ Configuration
CELERY_BROKER_URL=amqp://$RABBITMQ_USER:$RABBITMQ_PASSWORD@localhost:5672/$RABBITMQ_VHOST
CELERY_RESULT_BACKEND=django-db
CELERY_ACCEPT_CONTENT=['json']
CELERY_TASK_SERIALIZER=json
CELERY_RESULT_SERIALIZER=json
CELERY_TIMEZONE=UTC
CELERY_WORKERS=2
CELERY_WORKER_CONCURRENCY=4
CELERY_WORKER_MAX_TASKS_PER_CHILD=1000
CELERY_TASK_TIME_LIMIT=1800
CELERY_TASK_SOFT_TIME_LIMIT=1740

# Application Settings
SITE_NAME=ProEnergia
SITE_URL=https://$DOMAIN
EOF

# Set proper permissions
chown proenergia:proenergia "$ENV_FILE"
chmod 600 "$ENV_FILE"

echo "✓ Environment configuration created"

echo ""
echo "========================================================================="
echo "                    INFRASTRUCTURE SETUP COMPLETE                       "
echo "========================================================================="
echo ""
echo "IMPORTANT: Save these credentials securely!"
echo ""
echo "PostgreSQL:"
echo "  Database: $DB_NAME"
echo "  User: $DB_USER"
echo "  Password: $DB_PASSWORD"
echo ""
echo "RabbitMQ:"
echo "  User: $RABBITMQ_USER"
echo "  Password: $RABBITMQ_PASSWORD"
echo "  VHost: $RABBITMQ_VHOST"
echo ""
echo "Django:"
echo "  Secret Key: $DJANGO_SECRET_KEY"
echo ""
echo "Domain: $DOMAIN"
echo ""
echo "Environment file created at: $ENV_FILE"
echo ""
echo "PostgreSQL Optimizations Applied:"
echo "  shared_buffers: $SHARED_BUFFERS"
echo "  work_mem: $WORK_MEM"
echo "  maintenance_work_mem: $MAINTENANCE_WORK_MEM"
echo "  effective_cache_size: $EFFECTIVE_CACHE_SIZE"
echo ""
echo "========================================================================="
echo ""
echo "Next step: Run 02_setup_application.sh as the proenergia user"