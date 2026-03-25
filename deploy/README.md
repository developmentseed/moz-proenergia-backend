# ProEnergia Deployment Guide

Complete deployment guide for ProEnergia Django application on Ubuntu 24.04 LTS.

## Prerequisites

- **Server**: Ubuntu 24.04 LTS with minimum 4GB RAM (16GB+ recommended)
- **Domain**: A domain name pointing to your server's IP address
- **Access**: Root access to the server
- **Repository**: Access to https://github.com/developmentseed/moz-proenergia-backend (public repo)

## Quick Start

SSH into your server as root and run:

```bash
# Clone the repository
cd ~
git clone https://github.com/developmentseed/moz-proenergia-backend.git
cd moz-proenergia-backend/deploy/scripts

# Make scripts executable
chmod +x *.sh

# Run setup scripts in order (DOMAIN IS REQUIRED)
./00_setup_system.sh                                    # Install system dependencies
./01_setup_infrastructure.sh your-domain.com           # Setup PostgreSQL, RabbitMQ, generate .env (REQUIRED: domain)
sudo -u proenergia ./02_setup_application.sh           # Install application
./03_setup_services.sh your-domain.com admin@email.com # Configure services and SSL (REQUIRED: domain, OPTIONAL: email)
./04_verify_setup.sh                                   # Verify installation

# Clean up temporary checkout (optional)
cd ~ && rm -rf moz-proenergia-backend
```

## Detailed Setup Steps

### Step 1: System Dependencies

```bash
./00_setup_system.sh
```

This script:
- Updates system packages
- Installs PostgreSQL 16 with PostGIS
- Installs RabbitMQ for Celery task queue
- Installs nginx web server
- Installs Python and development tools
- Creates the `proenergia` system user
- Sets up application directories

### Step 2: Infrastructure Setup

```bash
./01_setup_infrastructure.sh your-domain.com  # Domain parameter is REQUIRED
```

This script:
- Configures PostgreSQL database with secure password
- Optimizes PostgreSQL for performance
- Sets up RabbitMQ with secure credentials
- Generates Django secret key
- Creates complete `.env` configuration file
- **Displays all generated credentials** - Save these securely!

**Important**: This script generates and displays:
- PostgreSQL password
- RabbitMQ password
- Django secret key

Save these credentials immediately as they won't be shown again.

### Step 3: Application Setup

```bash
sudo -u proenergia ./02_setup_application.sh
```

This script (run as proenergia user):
- Clones the application repository to `/var/www/proenergia/app`
- Creates Python virtual environment
- Installs Python dependencies
- Runs database migrations
- Creates cache tables
- Collects static files
- Compiles translation files

### Step 4: Services Configuration

```bash
./03_setup_services.sh your-domain.com admin@your-domain.com  # Domain is REQUIRED, email is optional
```

This script:
- Configures nginx with your domain
- Sets up SSL certificate via Let's Encrypt
- Configures Gunicorn application server
- Sets up Celery worker and beat services
- Configures deployment webhook
- Starts all services
- **Displays webhook secret** for GitHub integration

### Step 5: Verification

```bash
./04_verify_setup.sh
```

This script verifies:
- All services are running
- Database connection works
- Web application is accessible
- File permissions are correct
- System resources are adequate

## Post-Installation

### Create Django Admin User

```bash
cd /var/www/proenergia/app
source venv/bin/activate
python manage.py createsuperuser
```

### Configure GitHub Webhook (Optional)

For automated deployment on push to main branch:

1. Go to GitHub repository → Settings → Webhooks → Add webhook
2. **Payload URL**: `https://your-domain.com/deploy-webhook`
3. **Content type**: `application/json`
4. **Secret**: Use the webhook secret displayed during setup
5. **Events**: Select "Just the push event"
6. Click "Add webhook"

### Manual Deployment

To manually deploy latest changes:

```bash
sudo deploy-proenergia
```

## Service Management

### Application Services

```bash
# Main application
sudo systemctl status proenergia
sudo systemctl restart proenergia
sudo journalctl -u proenergia -f

# Celery worker
sudo systemctl status proenergia-celery
sudo systemctl restart proenergia-celery
sudo journalctl -u proenergia-celery -f

# Celery beat scheduler
sudo systemctl status proenergia-celerybeat
sudo systemctl restart proenergia-celerybeat
sudo journalctl -u proenergia-celerybeat -f

# Webhook listener
sudo systemctl status proenergia-webhook
sudo systemctl restart proenergia-webhook
sudo journalctl -u proenergia-webhook -f
```

### System Services

```bash
# PostgreSQL
sudo systemctl status postgresql
sudo -u postgres psql

# RabbitMQ
sudo systemctl status rabbitmq-server
sudo rabbitmqctl status

# Nginx
sudo systemctl status nginx
sudo nginx -t  # Test configuration
sudo nginx -s reload  # Reload configuration
```

## File Locations

- **Application**: `/var/www/proenergia/app/`
- **Environment Config**: `/var/www/proenergia/app/.env`
- **Static Files**: `/var/www/proenergia/app/staticfiles/`
- **Media Files**: `/var/www/proenergia/app/media/`
- **Logs**: `/var/log/proenergia/`
- **Nginx Config**: `/etc/nginx/sites-available/proenergia.conf`
- **Systemd Services**: `/etc/systemd/system/proenergia*.service`

## Troubleshooting

### Check Service Status

```bash
# Quick status check of all services
./04_verify_setup.sh
```

### Common Issues

#### Application won't start
```bash
# Check logs
sudo journalctl -u proenergia -n 100

# Verify environment file
sudo -u proenergia cat /var/www/proenergia/app/.env

# Test Django directly
cd /var/www/proenergia/app
source venv/bin/activate
python manage.py check
```

#### Database connection issues
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection
sudo -u postgres psql -d proenergia_db

# Check authentication
grep proenergia /etc/postgresql/16/main/pg_hba.conf
```

#### Celery not processing tasks
```bash
# Check RabbitMQ
sudo rabbitmqctl status

# Check Celery worker
sudo systemctl status proenergia-celery
sudo journalctl -u proenergia-celery -n 50

# Test RabbitMQ connection
sudo rabbitmqctl list_users
sudo rabbitmqctl list_vhosts
```

#### SSL certificate issues
```bash
# Test certificate renewal
sudo certbot renew --dry-run

# Check nginx SSL configuration
sudo nginx -t
grep ssl /etc/nginx/sites-available/proenergia.conf
```

### Rollback Deployment

If a deployment fails:

```bash
cd /var/www/proenergia/app
git log --oneline -5  # Find previous commit
git checkout <previous-commit-hash>
sudo systemctl restart proenergia
```

## Security Considerations

1. **Passwords**: All passwords are auto-generated during setup
2. **Firewall**: Configure UFW to only allow necessary ports
3. **SSL**: Automatically configured with Let's Encrypt
4. **File Permissions**: Properly set during installation
5. **Database**: Uses password authentication, not trust

## Performance Tuning

PostgreSQL optimizations are automatically applied based on system RAM during setup:
- Shared buffers
- Work memory
- Maintenance work memory
- Checkpoint settings
- Autovacuum configuration

Monitor performance:
```bash
# Database slow queries
sudo -u postgres psql -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"

# System resources
htop
df -h
free -m
```

## Backup and Recovery

### Database Backup
```bash
# Backup database
sudo -u postgres pg_dump proenergia_db > backup_$(date +%Y%m%d).sql

# Restore database
sudo -u postgres psql proenergia_db < backup_20240101.sql
```

### Application Backup
```bash
# Backup media files
tar -czf media_backup_$(date +%Y%m%d).tar.gz /var/www/proenergia/app/media/

# Backup environment config
cp /var/www/proenergia/app/.env ~/env_backup_$(date +%Y%m%d)
```

## Support

For detailed debugging and advanced configurations, see [DEBUGGING.md](DEBUGGING.md).

For issues with the deployment process, please check:
1. All prerequisites are met
2. Scripts were run in the correct order
3. Domain DNS is properly configured
4. Server firewall allows HTTP/HTTPS traffic

## Script Reference

- `00_setup_system.sh` - Install system packages and create user
- `01_setup_infrastructure.sh <domain>` - Configure PostgreSQL, RabbitMQ, and generate .env (REQUIRES: domain parameter)
- `02_setup_application.sh` - Install Django application (run as proenergia user)
- `03_setup_services.sh <domain> [email]` - Configure nginx, SSL, and systemd services (REQUIRES: domain, OPTIONAL: email)
- `04_verify_setup.sh` - Verify installation completeness
- `05_update_app.sh` - Update application (used by deployment system)
- `deploy-wrapper.sh` - Deployment helper script