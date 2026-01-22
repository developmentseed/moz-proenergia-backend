# ProEnergia Deployment

This directory contains deployment scripts for the ProEnergia Django application on Ubuntu 24.04 LTS.

## Prerequisites

- Ubuntu 24.04 LTS server with 16GB+ RAM
- Domain name pointing to your server
- Root access to the server

## Initial Setup

Run these scripts in order as root:

### 1. System Setup
```bash
cd /root
git clone git@github.com:developmentseed/moz-proenergia-backend.git
cd moz-proenergia-backend/deploy
./scripts/01_setup_system.sh
```

### 2. Configure GitHub Access
```bash
# Generate SSH key for the proenergia user
sudo -u proenergia ssh-keygen -t ed25519 -C "deploy@your-server.com" -f /home/proenergia/.ssh/id_ed25519 -N ""

# Display the public key
sudo -u proenergia cat /home/proenergia/.ssh/id_ed25519.pub
```

Add this key to GitHub:
- Go to Repository Settings → Deploy Keys → Add Deploy Key
- Paste the public key and give it a name like "Production Server"

### 3. Application Setup
```bash
sudo -u proenergia ./scripts/02_setup_app.sh
```

### 4. Configure Environment
```bash
sudo -u proenergia nano /var/www/proenergia/app/.env
```
Update with your actual values (domain, database password, secret key).

### 5. Services & Webhook Setup
```bash
./scripts/03_setup_services.sh your-domain.com admin@your-domain.com
```

This will:
- Configure nginx and SSL
- Set up the application service
- Install the deployment script
- **Set up the webhook listener and display a webhook secret**

### 6. Configure GitHub Webhook

Using the webhook secret displayed in step 5:

1. Go to your repository Settings → Webhooks → Add webhook
2. **Payload URL**: `https://your-domain.com/deploy-webhook`
3. **Content type**: `application/json`
4. **Secret**: Enter the webhook secret from step 5
5. **Events**: Select "Just the push event"
6. Click "Add webhook"

## Deployment

### Automatic Deployment
Once configured, pushes to the `main` branch automatically deploy to your server.

### Manual Deployment
To manually deploy the latest changes:

```bash
ssh ubuntu@your-server.com 'sudo deploy-proenergia'
```

## Service Management

```bash
# Check application status
sudo systemctl status proenergia

# View application logs
sudo journalctl -u proenergia -f

# Restart application
sudo systemctl restart proenergia
```

## File Locations

- **Application**: `/var/www/proenergia/app/`
- **Logs**: `/var/log/proenergia/`
- **Deploy script**: `/usr/local/bin/deploy-proenergia`

## Troubleshooting

For detailed troubleshooting, monitoring, and rollback procedures, see [DEBUGGING.md](DEBUGGING.md).