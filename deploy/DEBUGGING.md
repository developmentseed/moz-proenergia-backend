# ProEnergia Deployment Debugging Guide

This document contains detailed troubleshooting information for the ProEnergia deployment.

## Architecture Overview

- **Web Server**: Nginx (reverse proxy, static files, SSL termination)
- **Application Server**: Gunicorn (WSGI server)
- **Database**: PostgreSQL 16 with PostGIS extension
- **Message Broker**: RabbitMQ (for Celery)
- **Task Queue**: Celery (background tasks and scheduling)
- **Process Management**: systemd
- **Deployment**: Webhook listener + deployment wrapper script

## Complete File Locations

- **Application**: `/var/www/proenergia/app/`
- **Virtual Environment**: `/var/www/proenergia/app/venv/`
- **Environment File**: `/var/www/proenergia/app/.env`
- **Logs Directory**: `/var/log/proenergia/`
- **Deployment Log**: `/var/log/proenergia/deployment.log`
- **Gunicorn Error Log**: `/var/log/proenergia/gunicorn_error.log`
- **Nginx Config**: `/etc/nginx/sites-available/proenergia.conf`
- **Systemd Service**: `/etc/systemd/system/proenergia.service`
- **Webhook Service**: `/etc/systemd/system/proenergia-webhook.service`
- **Webhook Listener**: `/var/www/proenergia/webhook/webhook_listener.py`
- **Gunicorn Config**: `/etc/gunicorn/gunicorn.conf.py`
- **Deploy Script**: `/usr/local/bin/deploy-proenergia`
- **Update Script**: `/var/www/proenergia/app/deploy/scripts/04_update_app_nosudo.sh`
- **Sudoers Config**: `/etc/sudoers.d/proenergia-deploy`
- **Celery Worker Service**: `/etc/systemd/system/proenergia-celery.service`
- **Celery Beat Service**: `/etc/systemd/system/proenergia-celerybeat.service`

## Monitoring

### Deployment Monitoring
```bash
# Watch deployment logs in real-time
tail -f /var/log/proenergia/deployment.log

# Check last deployment status
grep "completed successfully" /var/log/proenergia/deployment.log | tail -1

# View all deployment errors
grep "ERROR" /var/log/proenergia/deployment.log
```

### Webhook Monitoring
```bash
# Check webhook listener status
sudo systemctl status proenergia-webhook

# View webhook logs
sudo journalctl -u proenergia-webhook -f

# Test webhook endpoint
curl -X POST https://your-domain.com/deploy-webhook

# Check nginx webhook access logs
tail -f /var/log/nginx/webhook_access.log
tail -f /var/log/nginx/webhook_error.log
```

### Application Monitoring
```bash
# Check application service
sudo systemctl status proenergia

# View application logs
sudo journalctl -u proenergia -f

# Check Gunicorn error logs
tail -f /var/log/proenergia/gunicorn_error.log

# Monitor resource usage
htop  # or top
```

### Celery and RabbitMQ Monitoring
```bash
# Check Celery worker status
sudo systemctl status proenergia-celery

# Check Celery beat status
sudo systemctl status proenergia-celerybeat

# View Celery worker logs
sudo journalctl -u proenergia-celery -f

# View Celery beat logs
sudo journalctl -u proenergia-celerybeat -f

# Check RabbitMQ status
sudo systemctl status rabbitmq-server
sudo rabbitmqctl status

# List RabbitMQ queues
sudo rabbitmqctl list_queues name messages consumers

# Check RabbitMQ users and vhosts
sudo rabbitmqctl list_users
sudo rabbitmqctl list_vhosts

# Monitor Celery tasks (from app directory)
cd /var/www/proenergia/app
sudo -u proenergia bash -c "source venv/bin/activate && celery -A proenergia inspect active"
sudo -u proenergia bash -c "source venv/bin/activate && celery -A proenergia inspect stats"
```

## Common Issues and Solutions

### Application Won't Start
1. Check service status:
   ```bash
   sudo systemctl status proenergia
   sudo journalctl -u proenergia -n 50
   ```

2. Verify environment file:
   ```bash
   sudo -u proenergia cat /var/www/proenergia/app/.env
   # Check for missing or incorrect values
   ```

3. Test Django directly:
   ```bash
   cd /var/www/proenergia/app
   sudo -u proenergia bash -c "source venv/bin/activate && python manage.py check"
   ```

4. Check database connectivity:
   ```bash
   sudo -u postgres psql -c "\l"  # List databases
   sudo -u postgres psql proenergia_db -c "\dt"  # List tables
   ```

### 502 Bad Gateway
This means nginx can't connect to Gunicorn.

1. Verify Gunicorn is running:
   ```bash
   sudo systemctl status proenergia
   ps aux | grep gunicorn
   ```

2. Check Gunicorn socket/port:
   ```bash
   ss -tulpn | grep 8000  # If using port
   ls -la /var/run/proenergia/  # If using socket
   ```

3. Review Gunicorn configuration:
   ```bash
   cat /etc/gunicorn/gunicorn.conf.py
   ```

4. Check for port conflicts:
   ```bash
   sudo lsof -i :8000
   ```

### Webhook Not Triggering Deployments

1. Verify webhook listener is running:
   ```bash
   sudo systemctl status proenergia-webhook
   ```

2. Check webhook secret matches GitHub:
   ```bash
   sudo grep WEBHOOK_SECRET /etc/systemd/system/proenergia-webhook.service
   ```

3. Test webhook manually:
   ```bash
   # From GitHub webhook settings, use "Redeliver" on a recent delivery
   # Or test locally:
   curl -X POST http://localhost:9001/health
   ```

4. Check nginx configuration:
   ```bash
   grep -A 10 "deploy-webhook" /etc/nginx/sites-available/proenergia.conf
   ```

5. Verify sudoers permissions:
   ```bash
   sudo cat /etc/sudoers.d/proenergia-deploy
   sudo -u proenergia sudo -l  # List allowed commands
   ```

### Deployment Fails

1. Check deployment log:
   ```bash
   tail -f /var/log/proenergia/deployment.log
   grep ERROR /var/log/proenergia/deployment.log | tail -10
   ```

2. Run deployment manually to see errors:
   ```bash
   sudo deploy-proenergia
   ```

3. Test individual components:
   ```bash
   # Test git access
   sudo -u proenergia bash -c "cd /var/www/proenergia/app && git fetch"
   
   # Test pip
   sudo -u proenergia bash -c "cd /var/www/proenergia/app && source venv/bin/activate && pip list"
   
   # Test migrations
   sudo -u proenergia bash -c "cd /var/www/proenergia/app && source venv/bin/activate && python manage.py showmigrations"
   ```

### SSL Certificate Issues

1. Check certificate status:
   ```bash
   sudo certbot certificates
   ```

2. Renew certificate manually:
   ```bash
   sudo certbot renew --dry-run  # Test first
   sudo certbot renew
   ```

3. Check auto-renewal:
   ```bash
   sudo systemctl status certbot.timer
   sudo journalctl -u certbot.timer
   ```

### Celery Worker Not Processing Tasks

1. Check worker is running:
   ```bash
   sudo systemctl status proenergia-celery
   ps aux | grep celery
   ```

2. Check RabbitMQ connectivity:
   ```bash
   sudo rabbitmqctl status
   sudo rabbitmqctl list_queues
   ```

3. Verify broker URL in .env:
   ```bash
   sudo grep CELERY_BROKER_URL /var/www/proenergia/app/.env
   ```

4. Test Celery connection manually:
   ```bash
   cd /var/www/proenergia/app
   sudo -u proenergia bash -c "source venv/bin/activate && celery -A proenergia inspect ping"
   ```

5. Check for import errors:
   ```bash
   cd /var/www/proenergia/app
   sudo -u proenergia bash -c "source venv/bin/activate && python -c 'from proenergia.celery import app; print(app)'"
   ```

### Celery Tasks Timing Out

1. Check task time limits in .env:
   ```bash
   grep CELERY_TASK_TIME_LIMIT /var/www/proenergia/app/.env
   ```

2. Monitor long-running tasks:
   ```bash
   sudo -u proenergia bash -c "cd /var/www/proenergia/app && source venv/bin/activate && celery -A proenergia inspect active"
   ```

3. Increase time limits if needed:
   ```bash
   sudo nano /var/www/proenergia/app/.env
   # Update CELERY_TASK_TIME_LIMIT and CELERY_TASK_SOFT_TIME_LIMIT
   sudo systemctl restart proenergia-celery
   ```

### RabbitMQ Connection Refused

1. Check RabbitMQ is running:
   ```bash
   sudo systemctl status rabbitmq-server
   sudo systemctl start rabbitmq-server
   ```

2. Verify user permissions:
   ```bash
   sudo rabbitmqctl list_users
   sudo rabbitmqctl list_user_permissions proenergia
   ```

3. Reset RabbitMQ user if needed:
   ```bash
   sudo rabbitmqctl delete_user proenergia
   sudo rabbitmqctl add_user proenergia NEW_PASSWORD
   sudo rabbitmqctl set_permissions -p proenergia proenergia ".*" ".*" ".*"
   # Update password in /var/www/proenergia/app/.env
   sudo systemctl restart proenergia-celery
   ```

### Database Issues

1. Check PostgreSQL status:
   ```bash
   sudo systemctl status postgresql
   sudo journalctl -u postgresql
   ```

2. Test database connection:
   ```bash
   sudo -u postgres psql -d proenergia_db
   \conninfo  # Show connection info
   \q  # Quit
   ```

3. Check database size and performance:
   ```bash
   sudo -u postgres psql -d proenergia_db -c "SELECT pg_size_pretty(pg_database_size('proenergia_db'));"
   ```

### Permission Issues

1. Verify file ownership:
   ```bash
   ls -la /var/www/proenergia/
   ls -la /var/log/proenergia/
   ls -la /usr/local/bin/deploy-proenergia
   ```

2. Fix ownership if needed:
   ```bash
   sudo chown -R proenergia:proenergia /var/www/proenergia/
   sudo chown -R proenergia:proenergia /var/log/proenergia/
   ```

3. Check sudoers:
   ```bash
   sudo visudo -c  # Verify syntax
   ```

## Rollback Procedures

### Quick Rollback
Revert the last commit and redeploy:
```bash
ssh ubuntu@server 'cd /var/www/proenergia/app && sudo -u proenergia git revert HEAD --no-edit && sudo deploy-proenergia'
```

### Rollback to Specific Commit
```bash
# Find the commit you want
ssh ubuntu@server 'cd /var/www/proenergia/app && sudo -u proenergia git log --oneline -10'

# Reset to that commit
ssh ubuntu@server 'cd /var/www/proenergia/app && sudo -u proenergia git reset --hard COMMIT_HASH && sudo deploy-proenergia'
```

### Emergency Recovery
If the application is completely broken:

1. Stop the service:
   ```bash
   sudo systemctl stop proenergia
   ```

2. Restore from backup (if available):
   ```bash
   # Restore database
   sudo -u postgres psql proenergia_db < /path/to/backup.sql
   
   # Restore code to known good state
   cd /var/www/proenergia/app
   sudo -u proenergia git reset --hard LAST_KNOWN_GOOD_COMMIT
   ```

3. Restart:
   ```bash
   sudo deploy-proenergia
   ```

## Performance Tuning

### Gunicorn Workers
Current setting: `CPU cores * 2 + 1`

To adjust:
```bash
sudo nano /etc/gunicorn/gunicorn.conf.py
# Modify workers setting
sudo systemctl restart proenergia
```

### Memory Limits
Current: 8GB soft, 10GB hard

To adjust:
```bash
sudo nano /etc/systemd/system/proenergia.service
# Modify MemoryHigh and MemoryMax
sudo systemctl daemon-reload
sudo systemctl restart proenergia
```

### Database Optimization
```bash
# Analyze and vacuum database
sudo -u postgres psql -d proenergia_db -c "ANALYZE;"
sudo -u postgres psql -d proenergia_db -c "VACUUM ANALYZE;"

# Check slow queries
sudo -u postgres psql -d proenergia_db -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"
```

### Static File Caching
Currently set to 1 day in nginx. To modify:
```bash
sudo nano /etc/nginx/sites-available/proenergia.conf
# Adjust expires directive in location /static/ block
sudo nginx -t && sudo systemctl reload nginx
```

## Logs Rotation

Logs are automatically rotated by systemd-journald and logrotate. To check configuration:
```bash
cat /etc/logrotate.d/proenergia  # If exists
journalctl --disk-usage  # Check journal size
```

## Security Checklist

- [ ] Environment file permissions: `600` (read/write owner only)
- [ ] Webhook secret is strong (32+ characters)
- [ ] Database password is unique and strong
- [ ] Django SECRET_KEY is unique and never committed to git
- [ ] SSL certificate is valid and auto-renewing
- [ ] Firewall is configured (ufw)
- [ ] Fail2ban is configured for SSH (optional but recommended)
- [ ] Regular security updates: `sudo apt update && sudo apt upgrade`

## Getting Help

1. Check this guide first
2. Review logs for specific error messages
3. Search for the error message online
4. Check Django/Gunicorn/Nginx documentation
5. Contact system administrator or development team

## Useful Commands Reference

```bash
# Service management
sudo systemctl {start|stop|restart|status} proenergia
sudo systemctl {start|stop|restart|status} proenergia-webhook
sudo systemctl {start|stop|restart|status} proenergia-celery
sudo systemctl {start|stop|restart|status} proenergia-celerybeat
sudo systemctl {start|stop|restart|status} rabbitmq-server
sudo systemctl {start|stop|restart|status} nginx
sudo systemctl {start|stop|restart|status} postgresql

# Log viewing
sudo journalctl -u proenergia -f          # App logs
sudo journalctl -u proenergia-webhook -f  # Webhook logs
sudo journalctl -u proenergia-celery -f    # Celery worker logs
sudo journalctl -u proenergia-celerybeat -f # Celery beat logs
tail -f /var/log/proenergia/*.log        # All ProEnergia logs
tail -f /var/log/nginx/*.log             # Nginx logs

# Deployment
sudo deploy-proenergia                    # Manual deploy
sudo -u proenergia /var/www/proenergia/app/deploy/scripts/04_update_app_nosudo.sh  # Update without restart

# Testing
curl -I https://your-domain.com          # Test HTTPS
curl http://localhost:8000/admin/        # Test app directly
```