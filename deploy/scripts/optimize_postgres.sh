#!/bin/bash
set -e

echo "=== Optimizing PostgreSQL Configuration ==="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)"
   exit 1
fi

PG_VERSION="16"
PG_CONFIG_DIR="/etc/postgresql/$PG_VERSION/main"
PG_CONFIG_FILE="$PG_CONFIG_DIR/postgresql.conf"

# Get system memory in MB
TOTAL_MEM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_MEM_MB=$((TOTAL_MEM_KB / 1024))

echo "System memory: ${TOTAL_MEM_MB}MB"

# Backup original configuration
cp "$PG_CONFIG_FILE" "$PG_CONFIG_FILE.backup.$(date +%Y%m%d_%H%M%S)"
echo "Backed up original config to $PG_CONFIG_FILE.backup.$(date +%Y%m%d_%H%M%S)"

# Function to update or add configuration parameter
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

echo "=== Applying ProEnergia optimizations ==="

# Memory settings
# shared_buffers: 25% of RAM (max 8GB for 16GB+ systems)
if [ $TOTAL_MEM_MB -ge 16384 ]; then
    SHARED_BUFFERS="4GB"
elif [ $TOTAL_MEM_MB -ge 8192 ]; then
    SHARED_BUFFERS="2GB"
elif [ $TOTAL_MEM_MB -ge 4096 ]; then
    SHARED_BUFFERS="1GB"
else
    SHARED_BUFFERS="256MB"
fi

# work_mem: For complex queries with sorting/aggregation
# Conservative setting: Total RAM / max_connections / 4
WORK_MEM="32MB"

# maintenance_work_mem: For maintenance operations like VACUUM
MAINTENANCE_WORK_MEM="512MB"

# effective_cache_size: OS cache estimate (50-75% of RAM)
EFFECTIVE_CACHE_SIZE="$((TOTAL_MEM_MB * 3 / 4))MB"

echo "Configuring memory settings..."
update_pg_config "shared_buffers" "$SHARED_BUFFERS"
update_pg_config "work_mem" "$WORK_MEM"
update_pg_config "maintenance_work_mem" "$MAINTENANCE_WORK_MEM"
update_pg_config "effective_cache_size" "$EFFECTIVE_CACHE_SIZE"

# Connection settings
echo "Configuring connection settings..."
update_pg_config "max_connections" "200"
update_pg_config "superuser_reserved_connections" "5"

# Checkpoint settings for better write performance
echo "Configuring checkpoint settings..."
update_pg_config "checkpoint_completion_target" "0.9"
update_pg_config "wal_buffers" "16MB"
update_pg_config "checkpoint_segments" "32"  # For older versions
update_pg_config "max_wal_size" "2GB"        # For newer versions
update_pg_config "min_wal_size" "512MB"

# Query planner settings
echo "Configuring query planner..."
update_pg_config "random_page_cost" "1.1"  # For SSD storage
update_pg_config "effective_io_concurrency" "200"  # For SSD
update_pg_config "default_statistics_target" "100"

# Autovacuum settings (important for performance)
echo "Configuring autovacuum..."
update_pg_config "autovacuum" "on"
update_pg_config "autovacuum_max_workers" "4"
update_pg_config "autovacuum_naptime" "30s"
update_pg_config "autovacuum_vacuum_threshold" "50"
update_pg_config "autovacuum_vacuum_scale_factor" "0.1"
update_pg_config "autovacuum_analyze_threshold" "50"
update_pg_config "autovacuum_analyze_scale_factor" "0.05"

# Logging settings for monitoring
echo "Configuring logging..."
update_pg_config "log_min_duration_statement" "1000"  # Log queries > 1 second
update_pg_config "log_checkpoints" "on"
update_pg_config "log_connections" "on"
update_pg_config "log_disconnections" "on"
update_pg_config "log_lock_waits" "on"
update_pg_config "log_temp_files" "0"
update_pg_config "log_autovacuum_min_duration" "0"

# Statement timeout to prevent long-running queries
update_pg_config "statement_timeout" "600000"  # 10 minutes

# Lock timeout
update_pg_config "lock_timeout" "10000"  # 10 seconds

# Idle transaction timeout
update_pg_config "idle_in_transaction_session_timeout" "300000"  # 5 minutes

echo "=== PostGIS specific optimizations ==="

# PostGIS specific settings
update_pg_config "postgis.gdal_enabled_drivers" "ENABLE_ALL"
update_pg_config "postgis.enable_outdb_rasters" "true"

echo "=== Restarting PostgreSQL to apply changes ==="
systemctl restart postgresql

# Wait for PostgreSQL to be ready
sleep 5

# Test connection
sudo -u postgres psql -c "SELECT version();" > /dev/null 2>&1 && \
    echo "✓ PostgreSQL restarted successfully" || \
    echo "✗ PostgreSQL restart failed - check logs: journalctl -u postgresql"

echo ""
echo "=== PostgreSQL optimization complete ==="
echo ""
echo "Configuration summary:"
echo "  shared_buffers: $SHARED_BUFFERS"
echo "  work_mem: $WORK_MEM"
echo "  maintenance_work_mem: $MAINTENANCE_WORK_MEM"
echo "  effective_cache_size: $EFFECTIVE_CACHE_SIZE"
echo "  max_connections: 200"
echo ""
echo "Monitor performance with:"
echo "  sudo -u postgres psql -c 'SELECT * FROM pg_stat_activity;'"
echo "  sudo -u postgres psql -c 'SELECT * FROM pg_stat_database;'"
echo ""
echo "Check slow queries in log:"
echo "  grep 'duration:' /var/log/postgresql/postgresql-$PG_VERSION-main.log"