#!/bin/bash
set -e

echo "=== Setting up all services (nginx, systemd, Celery, webhook) ==="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)"
   exit 1
fi

# Check for required domain parameter
if [ $# -eq 0 ] || [ -z "$1" ]; then
    echo "Error: Domain parameter is required"
    echo "Usage: $0 <domain> [email]"
    echo "Example: $0 example.com admin@example.com"
    exit 1
fi

DOMAIN="$1"
EMAIL=${2:-"admin@$DOMAIN"}

echo "Setting up services for domain: $DOMAIN"
echo "SSL certificate email: $EMAIL"

# Verify application exists
if [ ! -d "/var/www/proenergia/app" ]; then
    echo "Error: Application not found at /var/www/proenergia/app"
    echo "Please run 02_setup_application.sh first"
    exit 1
fi

echo ""
echo "=== Step 1: Configuring nginx ==="

# Copy nginx configuration
echo "Installing nginx configuration..."
cp /var/www/proenergia/app/deploy/configs/nginx/proenergia.conf /etc/nginx/sites-available/
sed -i "s/your-domain.com/$DOMAIN/g" /etc/nginx/sites-available/proenergia.conf

# Enable nginx site
ln -sf /etc/nginx/sites-available/proenergia.conf /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test nginx configuration
nginx -t

echo ""
echo "=== Step 2: Setting up Gunicorn service ==="

# Copy systemd service
echo "Installing systemd service..."
cp /var/www/proenergia/app/deploy/configs/systemd/proenergia.service /etc/systemd/system/

# Copy gunicorn configuration
echo "Installing gunicorn configuration..."
mkdir -p /etc/gunicorn
cp /var/www/proenergia/app/deploy/configs/gunicorn/gunicorn.conf.py /etc/gunicorn/

# Create runtime directory for gunicorn pidfile
mkdir -p /var/run/proenergia
chown proenergia:proenergia /var/run/proenergia

# Create tmpfiles.d config to recreate directory on boot
echo "d /var/run/proenergia 0755 proenergia proenergia -" > /etc/tmpfiles.d/proenergia.conf

echo ""
echo "=== Step 3: Setting up Celery services ==="

# Copy Celery worker and beat services
echo "Installing Celery services..."
cp /var/www/proenergia/app/deploy/configs/systemd/proenergia-celery.service /etc/systemd/system/
cp /var/www/proenergia/app/deploy/configs/systemd/proenergia-celerybeat.service /etc/systemd/system/

# Create runtime directory for Celery
mkdir -p /var/run/proenergia-celery
chown proenergia:proenergia /var/run/proenergia-celery

# Create tmpfiles.d config for Celery
echo "d /var/run/proenergia-celery 0755 proenergia proenergia -" > /etc/tmpfiles.d/proenergia-celery.conf

echo ""
echo "=== Step 4: Setting up deployment webhook ==="

# Create webhook directory
mkdir -p /var/www/proenergia/webhook

# Copy webhook listener
cp /var/www/proenergia/app/deploy/webhook/webhook_listener.py /var/www/proenergia/webhook/
chown -R proenergia:proenergia /var/www/proenergia/webhook

# Install webhook systemd service
cp /var/www/proenergia/app/deploy/configs/systemd/proenergia-webhook.service /etc/systemd/system/

# Generate webhook secret
WEBHOOK_SECRET=$(openssl rand -hex 32)

# Update service file with the secret
sed -i "s/CHANGE_ME_TO_SECURE_SECRET/$WEBHOOK_SECRET/" /etc/systemd/system/proenergia-webhook.service

# Save webhook secret for reference
WEBHOOK_SECRET_FILE="/var/www/proenergia/webhook_secret.txt"
echo "$WEBHOOK_SECRET" > "$WEBHOOK_SECRET_FILE"
chmod 600 "$WEBHOOK_SECRET_FILE"
chown proenergia:proenergia "$WEBHOOK_SECRET_FILE"

echo ""
echo "=== Step 5: Installing deployment tools ==="

# Install deployment wrapper script
echo "Installing deployment wrapper script..."
cp /var/www/proenergia/app/deploy/scripts/deploy-wrapper.sh /usr/local/bin/deploy-proenergia
chmod +x /usr/local/bin/deploy-proenergia

# Install sudoers configuration for deployment
echo "Configuring deployment permissions..."
cp /var/www/proenergia/app/deploy/configs/sudoers/proenergia-deploy /etc/sudoers.d/
chmod 440 /etc/sudoers.d/proenergia-deploy
visudo -c || echo "WARNING: Sudoers syntax check failed - please review manually"

# Make update script executable (will be renamed to 05_update_app.sh later)
if [ -f "/var/www/proenergia/app/deploy/scripts/05_update_app.sh" ]; then
    chmod +x /var/www/proenergia/app/deploy/scripts/05_update_app.sh
elif [ -f "/var/www/proenergia/app/deploy/scripts/04_update_app_nosudo.sh" ]; then
    chmod +x /var/www/proenergia/app/deploy/scripts/04_update_app_nosudo.sh
fi

echo ""
echo "=== Step 6: Starting all services ==="

# Reload systemd
systemctl daemon-reload

# Enable and start main application service
systemctl enable proenergia
systemctl start proenergia

# Enable and start Celery services
systemctl enable proenergia-celery
systemctl enable proenergia-celerybeat
systemctl start proenergia-celery
systemctl start proenergia-celerybeat

# Enable and start webhook service
systemctl enable proenergia-webhook
systemctl start proenergia-webhook

# Reload nginx
systemctl reload nginx

echo ""
echo "=== Step 7: Setting up SSL certificate ==="

# Setup SSL with Let's Encrypt
echo "Setting up SSL certificate..."
certbot --nginx -d $DOMAIN --email $EMAIL --agree-tos --non-interactive --redirect || {
    echo ""
    echo "WARNING: SSL certificate setup failed. The application will run on HTTP only."
    echo "To retry SSL setup later, run:"
    echo "  sudo certbot --nginx -d $DOMAIN --email $EMAIL --agree-tos --non-interactive --redirect"
    echo ""
}

# Setup auto-renewal (only if certbot is installed)
if command -v certbot &> /dev/null; then
    systemctl enable certbot.timer 2>/dev/null || true
    systemctl start certbot.timer 2>/dev/null || true
fi

echo ""
echo "=== Step 8: Configuring firewall ==="

# Open firewall ports if ufw is active
if ufw status | grep -q "Status: active"; then
    echo "Configuring firewall..."
    ufw allow 'Nginx Full'
    ufw allow ssh
fi

echo ""
echo "=== Checking service status ==="

# Check all services
echo ""
echo "Service Status:"
echo "---------------"
systemctl is-active --quiet proenergia && echo "✓ ProEnergia: Running" || echo "✗ ProEnergia: Not running"
systemctl is-active --quiet proenergia-celery && echo "✓ Celery Worker: Running" || echo "✗ Celery Worker: Not running"
systemctl is-active --quiet proenergia-celerybeat && echo "✓ Celery Beat: Running" || echo "✗ Celery Beat: Not running"
systemctl is-active --quiet proenergia-webhook && echo "✓ Webhook Listener: Running" || echo "✗ Webhook Listener: Not running"
systemctl is-active --quiet nginx && echo "✓ Nginx: Running" || echo "✗ Nginx: Not running"
systemctl is-active --quiet rabbitmq-server && echo "✓ RabbitMQ: Running" || echo "✗ RabbitMQ: Not running"
systemctl is-active --quiet postgresql && echo "✓ PostgreSQL: Running" || echo "✗ PostgreSQL: Not running"

echo ""
echo "========================================================================="
echo "                       SERVICES SETUP COMPLETE                          "
echo "========================================================================="
echo ""
echo "Your application should now be available at: https://$DOMAIN"
echo ""
echo "IMPORTANT: Configure GitHub webhook:"
echo "======================================"
echo "Webhook URL: https://$DOMAIN/deploy-webhook"
echo "Webhook Secret: $WEBHOOK_SECRET"
echo ""
echo "To configure in GitHub:"
echo "1. Go to your repository Settings → Webhooks → Add webhook"
echo "2. Payload URL: https://$DOMAIN/deploy-webhook"
echo "3. Content type: application/json"
echo "4. Secret: $WEBHOOK_SECRET"
echo "5. Select 'Just the push event'"
echo "6. Save the webhook"
echo ""
echo "Service Management Commands:"
echo "============================="
echo "Application:"
echo "  sudo systemctl status proenergia"
echo "  sudo systemctl restart proenergia"
echo "  sudo journalctl -u proenergia -f"
echo ""
echo "Celery:"
echo "  sudo systemctl status proenergia-celery"
echo "  sudo systemctl status proenergia-celerybeat"
echo "  sudo journalctl -u proenergia-celery -f"
echo ""
echo "Deployment:"
echo "  sudo deploy-proenergia  # Manual deployment"
echo ""
echo "Next step: Run ./04_verify_setup.sh to verify everything is working"