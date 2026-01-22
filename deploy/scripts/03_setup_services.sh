#!/bin/bash
set -e

echo "=== Setting up services (nginx, systemd) ==="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)"
   exit 1
fi

DOMAIN=${1:-"your-domain.com"}
EMAIL=${2:-"admin@your-domain.com"}

echo "Setting up services for domain: $DOMAIN"
echo "SSL certificate email: $EMAIL"

# Copy nginx configuration
echo "Installing nginx configuration..."
cp /var/www/proenergia/app/deploy/configs/nginx/proenergia.conf /etc/nginx/sites-available/
sed -i "s/your-domain.com/$DOMAIN/g" /etc/nginx/sites-available/proenergia.conf

# Enable nginx site
ln -sf /etc/nginx/sites-available/proenergia.conf /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test nginx configuration
nginx -t

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

# Reload systemd and enable services
systemctl daemon-reload
systemctl enable proenergia
systemctl start proenergia

# Reload nginx
systemctl reload nginx

# Setup SSL with Let's Encrypt
echo "Setting up SSL certificate..."
certbot --nginx -d $DOMAIN --email $EMAIL --agree-tos --non-interactive --redirect

# Setup auto-renewal
systemctl enable certbot.timer
systemctl start certbot.timer

# Install deployment wrapper script
echo "Installing deployment wrapper script..."
cp /var/www/proenergia/app/deploy/scripts/deploy-wrapper.sh /usr/local/bin/deploy-proenergia
chmod +x /usr/local/bin/deploy-proenergia

# Install sudoers configuration for deployment
echo "Configuring deployment permissions..."
cp /var/www/proenergia/app/deploy/configs/sudoers/proenergia-deploy /etc/sudoers.d/
chmod 440 /etc/sudoers.d/proenergia-deploy
visudo -c || echo "WARNING: Sudoers syntax check failed - please review manually"

# Make update script executable
chmod +x /var/www/proenergia/app/deploy/scripts/04_update_app_nosudo.sh

# Open firewall ports if ufw is active
if ufw status | grep -q "Status: active"; then
    echo "Configuring firewall..."
    ufw allow 'Nginx Full'
    ufw allow ssh
fi

# Setup automated deployment webhook
echo ""
echo "Setting up automated deployment webhook..."
/var/www/proenergia/app/deploy/scripts/05_setup_webhook.sh

echo ""
echo "=== Services setup complete ==="
echo "Your application should now be available at https://$DOMAIN"
echo ""
echo "Service management commands:"
echo "  sudo systemctl status proenergia    - Check service status"
echo "  sudo systemctl restart proenergia   - Restart application"
echo "  sudo journalctl -u proenergia -f    - View logs"
echo "  sudo nginx -s reload               - Reload nginx config"
echo ""
echo "Deployment commands:"
echo "  sudo deploy-proenergia             - Deploy latest changes from git"