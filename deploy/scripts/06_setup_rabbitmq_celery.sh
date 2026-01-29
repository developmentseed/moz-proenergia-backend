#!/bin/bash
set -e

echo "=== Setting up RabbitMQ and Celery ==="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)"
   exit 1
fi

echo "Installing RabbitMQ server..."
apt update
apt install -y rabbitmq-server

# Start and enable RabbitMQ
systemctl start rabbitmq-server
systemctl enable rabbitmq-server

echo "Configuring RabbitMQ..."

# Generate a secure password for RabbitMQ
RABBITMQ_PASSWORD=$(openssl rand -base64 32)

# Create RabbitMQ user and vhost for Celery
rabbitmqctl add_user proenergia "$RABBITMQ_PASSWORD" 2>/dev/null || echo "User already exists"
rabbitmqctl add_vhost proenergia 2>/dev/null || echo "Vhost already exists"
rabbitmqctl set_permissions -p proenergia proenergia ".*" ".*" ".*"
rabbitmqctl set_user_tags proenergia administrator

echo "Installing Celery systemd services..."

# Copy Celery worker service
cp /var/www/proenergia/app/deploy/configs/systemd/proenergia-celery.service /etc/systemd/system/
cp /var/www/proenergia/app/deploy/configs/systemd/proenergia-celerybeat.service /etc/systemd/system/

# Create runtime directory for Celery
mkdir -p /var/run/proenergia-celery
chown proenergia:proenergia /var/run/proenergia-celery

# Create tmpfiles.d config to recreate directory on boot
echo "d /var/run/proenergia-celery 0755 proenergia proenergia -" > /etc/tmpfiles.d/proenergia-celery.conf

# Update .env file with RabbitMQ connection string if not already present
ENV_FILE="/var/www/proenergia/app/.env"
if ! grep -q "CELERY_BROKER_URL" "$ENV_FILE"; then
    echo "" >> "$ENV_FILE"
    echo "# Celery Configuration" >> "$ENV_FILE"
    echo "CELERY_BROKER_URL=\"amqp://proenergia:${RABBITMQ_PASSWORD}@localhost:5672/proenergia\"" >> "$ENV_FILE"
    echo "CELERY_WORKERS=2" >> "$ENV_FILE"
    echo "CELERY_WORKER_CONCURRENCY=4" >> "$ENV_FILE"
    echo "CELERY_WORKER_MAX_TASKS_PER_CHILD=1000" >> "$ENV_FILE"
    echo "CELERY_TASK_TIME_LIMIT=1800" >> "$ENV_FILE"
    echo "CELERY_TASK_SOFT_TIME_LIMIT=1740" >> "$ENV_FILE"
fi

# Reload systemd and enable services
systemctl daemon-reload
systemctl enable proenergia-celery
systemctl enable proenergia-celerybeat

# Start services
systemctl start proenergia-celery
systemctl start proenergia-celerybeat

# Test RabbitMQ connection
if rabbitmqctl status > /dev/null 2>&1; then
    echo "✓ RabbitMQ is running"
else
    echo "✗ RabbitMQ failed to start"
    exit 1
fi

# Check Celery services
sleep 3
if systemctl is-active --quiet proenergia-celery; then
    echo "✓ Celery worker is running"
else
    echo "✗ Celery worker failed to start"
    echo "Check logs with: journalctl -u proenergia-celery -n 50"
fi

if systemctl is-active --quiet proenergia-celerybeat; then
    echo "✓ Celery beat is running"
else
    echo "✗ Celery beat failed to start"
    echo "Check logs with: journalctl -u proenergia-celerybeat -n 50"
fi

echo ""
echo "=== RabbitMQ and Celery setup complete ==="
echo ""
echo "Important: The RabbitMQ password has been set and saved to $ENV_FILE"
echo ""
echo "Service management commands:"
echo "  sudo systemctl status proenergia-celery      - Check Celery worker status"
echo "  sudo systemctl status proenergia-celerybeat  - Check Celery beat status"
echo "  sudo systemctl status rabbitmq-server        - Check RabbitMQ status"
echo ""
echo "View logs:"
echo "  sudo journalctl -u proenergia-celery -f      - Celery worker logs"
echo "  sudo journalctl -u proenergia-celerybeat -f  - Celery beat logs"
echo ""
echo "Test Celery:"
echo "  curl -X POST http://localhost:8000/api/v1/tasks/hello/ -H \"Content-Type: application/json\" -d '{\"name\": \"Test\"}'"