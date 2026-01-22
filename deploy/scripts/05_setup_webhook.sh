#!/bin/bash
set -e

echo "=== Setting up automated deployment webhook ==="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)"
   exit 1
fi

# Check if app directory exists
if [ ! -d "/var/www/proenergia/app" ]; then
    echo "Error: Application not found at /var/www/proenergia/app"
    echo "Please run 02_setup_app.sh first"
    exit 1
fi

echo "Installing webhook listener..."

# Create webhook directory
mkdir -p /var/www/proenergia/webhook

# Copy webhook listener
cp /var/www/proenergia/app/deploy/webhook/webhook_listener.py /var/www/proenergia/webhook/
chown -R proenergia:proenergia /var/www/proenergia/webhook

# Install systemd service
cp /var/www/proenergia/app/deploy/configs/systemd/proenergia-webhook.service /etc/systemd/system/

# Generate webhook secret
WEBHOOK_SECRET=$(openssl rand -hex 32)

# Update service file with the secret
sed -i "s/CHANGE_ME_TO_SECURE_SECRET/$WEBHOOK_SECRET/" /etc/systemd/system/proenergia-webhook.service

# Add sudoers permission for webhook to trigger deployment
if ! grep -q "proenergia ALL=(root) NOPASSWD: /usr/local/bin/deploy-proenergia" /etc/sudoers.d/proenergia-deploy 2>/dev/null; then
    echo "proenergia ALL=(root) NOPASSWD: /usr/local/bin/deploy-proenergia" >> /etc/sudoers.d/proenergia-deploy
    chmod 440 /etc/sudoers.d/proenergia-deploy
fi

# Start webhook service
echo "Starting webhook listener service..."
systemctl daemon-reload
systemctl enable proenergia-webhook
systemctl start proenergia-webhook

# Check if service started successfully
if systemctl is-active --quiet proenergia-webhook; then
    echo "✓ Webhook listener is running"
else
    echo "✗ Webhook listener failed to start"
    echo "Check logs: journalctl -u proenergia-webhook -f"
    exit 1
fi

# Add webhook location to nginx config if not already present
NGINX_CONFIG="/etc/nginx/sites-available/proenergia.conf"
if [ -f "$NGINX_CONFIG" ]; then
    if ! grep -q "/deploy-webhook" "$NGINX_CONFIG"; then
        echo "Adding webhook endpoint to nginx configuration..."
        
        # Insert webhook location before the closing } of server block
        sed -i '/^[[:space:]]*location \/ {/i\
    # Webhook endpoint for automated deployment\
    location /deploy-webhook {\
        limit_except POST { deny all; }\
        proxy_pass http://127.0.0.1:9001/webhook;\
        proxy_set_header Host $host;\
        proxy_set_header X-Real-IP $remote_addr;\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\
        proxy_pass_header X-GitHub-Event;\
        proxy_pass_header X-Hub-Signature-256;\
        proxy_pass_header X-GitHub-Delivery;\
        proxy_connect_timeout 10s;\
        proxy_send_timeout 10s;\
        proxy_read_timeout 10s;\
        access_log /var/log/nginx/webhook_access.log;\
        error_log /var/log/nginx/webhook_error.log;\
    }\
' "$NGINX_CONFIG"
        
        # Test and reload nginx
        if nginx -t; then
            systemctl reload nginx
            echo "✓ Nginx configuration updated"
        else
            echo "✗ Nginx configuration test failed"
            echo "Please check the configuration manually"
        fi
    else
        echo "Webhook endpoint already configured in nginx"
    fi
fi

echo ""
echo "=== Webhook setup complete ==="
echo ""
echo "IMPORTANT: Save these values to configure GitHub webhook:"
echo "========================================================="
echo "Webhook URL: https://your-domain.com/deploy-webhook"
echo "Webhook Secret: $WEBHOOK_SECRET"
echo "========================================================="
echo ""
echo "To configure in GitHub:"
echo "1. Go to your repository Settings → Webhooks → Add webhook"
echo "2. Enter the Webhook URL (replace your-domain.com with your actual domain)"
echo "3. Set Content type to: application/json"
echo "4. Enter the Webhook Secret shown above"
echo "5. Select 'Just the push event'"
echo "6. Save the webhook"
echo ""
echo "Once configured, pushes to the main branch will automatically deploy!"