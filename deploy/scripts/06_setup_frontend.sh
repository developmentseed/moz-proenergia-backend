#!/bin/bash
set -e

echo "=== Setting up ProEnergia frontend ==="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)"
   exit 1
fi

# Check for required domain parameter
if [ $# -eq 0 ] || [ -z "$1" ]; then
    echo "Error: Domain parameter is required"
    echo "Usage: $0 <frontend_domain> [email]"
    echo "Example: $0 frontend.example.com admin@example.com"
    exit 1
fi

DOMAIN="$1"
EMAIL=${2:-"admin@$DOMAIN"}
FRONTEND_DIR="/var/www/proenergia/frontend"
REPO_URL="https://github.com/developmentseed/moz-proenergia-web.git"

echo "Setting up frontend for domain: $DOMAIN"
echo "SSL certificate email: $EMAIL"

echo ""
echo "=== Step 1: Installing Node.js v24 ==="

curl -fsSL https://deb.nodesource.com/setup_24.x | bash -
apt-get install -y nodejs

echo "Node.js version: $(node --version)"

echo ""
echo "=== Step 2: Installing pnpm ==="

npm install -g pnpm
echo "pnpm version: $(pnpm --version)"

echo ""
echo "=== Step 3: Cloning frontend repository ==="

if [ -d "$FRONTEND_DIR" ]; then
    echo "Frontend directory already exists, pulling latest..."
    sudo -u proenergia bash -c "cd $FRONTEND_DIR && git fetch origin && git reset --hard origin/main"
else
    git clone "$REPO_URL" "$FRONTEND_DIR"
fi

chown -R proenergia:proenergia "$FRONTEND_DIR"

echo ""
echo "=== Step 4: Building frontend ==="

sudo -u proenergia bash -c "cd $FRONTEND_DIR && pnpm install && pnpm run build"

echo ""
echo "=== Step 5: Configuring nginx ==="

# Copy nginx configuration
cp /var/www/proenergia/app/deploy/configs/nginx/proenergia-frontend.conf /etc/nginx/sites-available/
sed -i "s/your-frontend-domain.com/$DOMAIN/g" /etc/nginx/sites-available/proenergia-frontend.conf

# Enable nginx site
ln -sf /etc/nginx/sites-available/proenergia-frontend.conf /etc/nginx/sites-enabled/

# Test nginx configuration
nginx -t

# Reload nginx
systemctl reload nginx

echo ""
echo "=== Step 6: Setting up SSL certificate ==="

certbot --nginx -d $DOMAIN --email $EMAIL --agree-tos --non-interactive --redirect || {
    echo ""
    echo "WARNING: SSL certificate setup failed. The frontend will run on HTTP only."
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
echo "========================================================================="
echo "                     FRONTEND SETUP COMPLETE                            "
echo "========================================================================="
echo ""
echo "Your frontend should now be available at: https://$DOMAIN"
echo ""
echo "To update the frontend later, run as proenergia user:"
echo "  sudo -u proenergia /var/www/proenergia/app/deploy/scripts/07_update_frontend.sh"
