# ProEnergia Deployment Guide

## Overview

This guide covers the improved deployment workflow for ProEnergia, including both manual single-command deployment and automated CI/CD integration.

## Solution 1: Single-Command Deployment

### Setup Instructions

1. **Install the deployment wrapper script** (on the server, as root):
```bash
# Copy the wrapper script
sudo cp /var/www/proenergia/app/deploy/scripts/deploy-wrapper.sh /usr/local/bin/deploy-proenergia
sudo chmod +x /usr/local/bin/deploy-proenergia

# Install sudoers configuration
sudo cp /var/www/proenergia/app/deploy/configs/sudoers/proenergia-deploy /etc/sudoers.d/
sudo chmod 440 /etc/sudoers.d/proenergia-deploy

# Verify sudoers syntax
sudo visudo -c
```

2. **Create deployment log directory**:
```bash
sudo mkdir -p /var/log/proenergia
sudo chown proenergia:proenergia /var/log/proenergia
```

### Usage

Deploy with a single command from your local machine:
```bash
ssh ubuntu@your-server.com 'sudo deploy-proenergia'
```

Or directly on the server:
```bash
sudo deploy-proenergia
```

### How It Works

The wrapper script (`deploy-proenergia`) handles the permission complexity:
- Runs as root (via sudo from ubuntu user)
- Executes git/Python operations as `proenergia` user
- Performs systemd operations as root
- Includes health checks and logging

## Solution 2: Automated CI/CD Deployment

### Option A: Webhook-Based Deployment (Recommended)

#### Server Setup

1. **Install webhook listener**:
```bash
# Copy webhook listener
sudo mkdir -p /var/www/proenergia/webhook
sudo cp /var/www/proenergia/app/deploy/webhook/webhook_listener.py /var/www/proenergia/webhook/
sudo chown -R proenergia:proenergia /var/www/proenergia/webhook

# Install systemd service
sudo cp /var/www/proenergia/app/deploy/configs/systemd/proenergia-webhook.service /etc/systemd/system/

# Generate a secure webhook secret
WEBHOOK_SECRET=$(openssl rand -hex 32)
echo "Save this secret for GitHub: $WEBHOOK_SECRET"

# Update the service file with your secret
sudo sed -i "s/CHANGE_ME_TO_SECURE_SECRET/$WEBHOOK_SECRET/" /etc/systemd/system/proenergia-webhook.service

# Add sudoers permission for webhook to trigger deployment
echo "proenergia ALL=(root) NOPASSWD: /usr/local/bin/deploy-proenergia" | sudo tee -a /etc/sudoers.d/proenergia-deploy

# Start the webhook listener
sudo systemctl daemon-reload
sudo systemctl enable proenergia-webhook
sudo systemctl start proenergia-webhook
```

2. **Configure Nginx**:
```bash
# Add webhook location to your nginx configuration
# Edit /etc/nginx/sites-available/proenergia.conf and add the webhook location block
# The content is provided in deploy/configs/nginx/webhook-location.conf

# After adding the location block:
sudo nginx -t
sudo systemctl reload nginx
```

3. **Configure GitHub**:
   - Go to your repository Settings → Webhooks → Add webhook
   - Payload URL: `https://your-domain.com/deploy-webhook`
   - Content type: `application/json`
   - Secret: Use the webhook secret generated above
   - Events: Select "Just the push event"
   - Active: ✓

4. **Configure GitHub Actions**:
   - Go to Settings → Secrets and variables → Actions
   - Add secret: `WEBHOOK_SECRET` (same value as above)
   - Add secret: `WEBHOOK_URL` (your deployment webhook URL)

#### GitHub Actions Workflow

The workflow (`.github/workflows/deploy.yml`) will:
1. Run tests on every push to main
2. Trigger deployment webhook on successful tests
3. The webhook listener validates the request and runs deployment

### Option B: SSH-Based Deployment (Alternative)

If you prefer direct SSH deployment:

1. **Generate deployment SSH key** (on your local machine):
```bash
ssh-keygen -t ed25519 -f ~/.ssh/proenergia-deploy -C "github-actions"
```

2. **Add public key to server**:
```bash
# Add to ubuntu user's authorized_keys
cat ~/.ssh/proenergia-deploy.pub | ssh ubuntu@your-server.com 'cat >> ~/.ssh/authorized_keys'
```

3. **Configure GitHub**:
   - Go to Settings → Secrets and variables → Actions
   - Add secret: `SSH_PRIVATE_KEY` (content of `~/.ssh/proenergia-deploy`)
   - Add secret: `HOST` (your server's IP or domain)

4. **Update workflow**:
   - Uncomment the `deploy-ssh` job in `.github/workflows/deploy.yml`
   - Comment out or remove the `deploy-webhook` job

## Comparison of Approaches

### Single-Command Deployment
**When to use**: Manual deployments, emergency fixes, testing

**Pros**:
- Simple and immediate
- No external dependencies
- Full control over timing

**Cons**:
- Manual process
- No automatic testing
- Requires SSH access

### Webhook-Based CI/CD
**When to use**: Production environments, team workflows

**Pros**:
- Fully automated
- Tests before deployment
- No SSH keys in GitHub
- Secure (validated signatures)

**Cons**:
- More complex setup
- Additional service to maintain

### SSH-Based CI/CD
**When to use**: Simple automation needs, private repositories

**Pros**:
- Simple GitHub Actions setup
- Direct deployment
- No additional services

**Cons**:
- SSH keys stored in GitHub
- Requires network access from GitHub

## Security Considerations

1. **Webhook Security**:
   - Always use HTTPS for webhook endpoint
   - Set a strong webhook secret
   - Consider IP whitelisting for GitHub webhooks
   - Monitor webhook logs regularly

2. **SSH Security**:
   - Use dedicated deployment keys
   - Restrict sudo permissions precisely
   - Regular audit of access logs

3. **General**:
   - Keep deployment scripts in version control
   - Review all changes before merging to main
   - Set up monitoring and alerting

## Troubleshooting

### Deployment fails with permission error
- Check sudoers configuration: `sudo visudo -c`
- Verify file ownership: `ls -la /usr/local/bin/deploy-proenergia`

### Webhook not triggering
- Check webhook listener status: `sudo systemctl status proenergia-webhook`
- Review logs: `sudo journalctl -u proenergia-webhook -f`
- Verify nginx configuration: `curl -X POST https://your-domain.com/deploy-webhook`

### Service won't restart
- Check service logs: `sudo journalctl -u proenergia -f`
- Verify service file syntax: `sudo systemctl daemon-reload`

## Monitoring

Set up monitoring for:
- Deployment success/failure (check logs in `/var/log/proenergia/deployment.log`)
- Webhook listener health: `curl http://localhost:9001/health`
- Application health after deployment

## Rollback Procedure

If a deployment causes issues:

1. **Quick rollback**:
```bash
ssh ubuntu@server 'cd /var/www/proenergia/app && sudo -u proenergia git revert HEAD && sudo deploy-proenergia'
```

2. **Specific commit rollback**:
```bash
ssh ubuntu@server 'cd /var/www/proenergia/app && sudo -u proenergia git reset --hard <commit-hash> && sudo deploy-proenergia'
```

## Best Practices

1. **Always test locally first**
2. **Use feature branches and PRs**
3. **Set up staging environment for testing**
4. **Monitor deployments actively**
5. **Keep deployment logs for audit**
6. **Regular backup of database before major deployments**
7. **Document any manual deployment steps**

## Next Steps

1. Start with Solution 1 (single-command) for immediate improvement
2. Set up webhook-based CI/CD for automation
3. Add deployment notifications (Slack, email, etc.)
4. Implement blue-green deployment for zero-downtime updates
5. Add automated rollback on health check failure