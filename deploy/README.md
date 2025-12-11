# ProEnergia Django Deployment

This directory contains deployment configurations and scripts for deploying the ProEnergia Django application on Ubuntu LTS.

## Prerequisites

- Ubuntu 24.04 LTS server
- 16GB RAM recommended
- Domain name pointing to the server
- Root access to the server

## Deployment Architecture

- **Web Server**: Nginx (reverse proxy, static files, SSL termination)
- **Application Server**: Gunicorn (WSGI server)
- **Database**: PostgreSQL 16 with PostGIS extension
- **Process Management**: systemd
- **SSL**: Let's Encrypt via certbot

## Quick Deployment

1. **System Setup** (as root):
```bash
./scripts/01_setup_system.sh
```

2. **Application Setup** (as proenergia user):
```bash
sudo -u proenergia ./scripts/02_setup_app.sh
```

3. **Configure Environment** (as proenergia user):
```bash
sudo -u proenergia nano /var/www/proenergia/app/.env
```
Update with your actual values (domain, database password, secret key)

4. **Services Setup** (as root):
```bash
./scripts/03_setup_services.sh your-domain.com admin@your-domain.com
```

## Environment Configuration

Copy `deploy/.env.production` to `/var/www/proenergia/app/.env` and update:

- `DJANGO_SECRET_KEY`: Generate a secure random key
- `ALLOWED_HOSTS`: Your domain name(s)
- `CSRF_TRUSTED_ORIGINS`: Your HTTPS domain(s)
- `DATABASE_URL`: Update password if changed

## Application Updates

To deploy updates:

```bash
sudo -u proenergia ./scripts/04_update_app.sh
```

## Service Management

```bash
# Check application status
sudo systemctl status proenergia

# Restart application
sudo systemctl restart proenergia

# View application logs
sudo journalctl -u proenergia -f

# Restart nginx
sudo systemctl restart nginx

# View nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

## File Locations

- **Application**: `/var/www/proenergia/app/`
- **Logs**: `/var/log/proenergia/`
- **Nginx Config**: `/etc/nginx/sites-available/proenergia.conf`
- **Systemd Service**: `/etc/systemd/system/proenergia.service`
- **Gunicorn Config**: `/etc/gunicorn/gunicorn.conf.py`

## Troubleshooting

### Application won't start
- Check logs: `sudo journalctl -u proenergia -f`
- Verify environment file exists and is readable
- Check database connectivity

### 502 Bad Gateway
- Verify gunicorn is running: `sudo systemctl status proenergia`
- Check gunicorn logs: `/var/log/proenergia/gunicorn_error.log`

### SSL Issues
- Renew certificate: `sudo certbot renew`
- Check certificate status: `sudo certbot certificates`

### Database Issues
- Check PostgreSQL status: `sudo systemctl status postgresql`
- Connect to database: `sudo -u postgres psql proenergia_db`

## Performance Tuning

- Gunicorn workers: Currently set to `CPU cores * 2 + 1`
- Memory limits: 8GB soft, 10GB hard (adjust based on usage)
- Static file caching: 1 day (configured in nginx)
- Consider adding Redis for caching if needed