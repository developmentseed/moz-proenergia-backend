#!/bin/bash
set -e

echo "=== ProEnergia Setup Verification ==="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track if any checks fail
FAILED_CHECKS=0

# Function to check service status
check_service() {
    local service=$1
    local display_name=$2
    
    if systemctl is-active --quiet $service; then
        echo -e "${GREEN}✓${NC} $display_name is running"
        return 0
    else
        echo -e "${RED}✗${NC} $display_name is not running"
        echo "  Check logs: sudo journalctl -u $service -n 50"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        return 1
    fi
}

# Function to test URL
test_url() {
    local url=$1
    local description=$2
    
    if curl -sSf -o /dev/null -w "%{http_code}" "$url" | grep -q "200\|301\|302"; then
        echo -e "${GREEN}✓${NC} $description is accessible"
        return 0
    else
        echo -e "${YELLOW}⚠${NC} $description may not be accessible (check manually)"
        return 1
    fi
}

echo "=== Step 1: Checking System Services ==="
echo ""

check_service "postgresql" "PostgreSQL"
check_service "rabbitmq-server" "RabbitMQ"
check_service "nginx" "Nginx"

echo ""
echo "=== Step 2: Checking Application Services ==="
echo ""

check_service "proenergia" "ProEnergia Application"
check_service "proenergia-celery" "Celery Worker"
check_service "proenergia-celerybeat" "Celery Beat"
check_service "proenergia-webhook" "Webhook Listener"

echo ""
echo "=== Step 3: Checking Database Connection ==="
echo ""

# Check if .env file exists
if [ -f "/var/www/proenergia/app/.env" ]; then
    echo -e "${GREEN}✓${NC} Environment file exists"
    
    # Extract database credentials from .env
    if [ -r "/var/www/proenergia/app/.env" ]; then
        DB_URL=$(grep "^DATABASE_URL=" /var/www/proenergia/app/.env | cut -d'=' -f2-)
        if [ ! -z "$DB_URL" ]; then
            # Parse database URL
            DB_USER=$(echo $DB_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
            DB_PASS=$(echo $DB_URL | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
            DB_NAME=$(echo $DB_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')
            
            # Test database connection
            PGPASSWORD="$DB_PASS" psql -U "$DB_USER" -d "$DB_NAME" -h localhost -c "SELECT 1;" > /dev/null 2>&1
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✓${NC} Database connection successful"
            else
                echo -e "${RED}✗${NC} Database connection failed"
                FAILED_CHECKS=$((FAILED_CHECKS + 1))
            fi
        else
            echo -e "${YELLOW}⚠${NC} Could not parse database URL from .env"
        fi
    else
        echo -e "${YELLOW}⚠${NC} Cannot read .env file (permission issue)"
    fi
else
    echo -e "${RED}✗${NC} Environment file not found at /var/www/proenergia/app/.env"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
fi

echo ""
echo "=== Step 4: Checking File Permissions ==="
echo ""

# Check directory ownership
if [ -d "/var/www/proenergia" ]; then
    OWNER=$(stat -c '%U' /var/www/proenergia/app 2>/dev/null)
    if [ "$OWNER" = "proenergia" ]; then
        echo -e "${GREEN}✓${NC} Application directory ownership is correct"
    else
        echo -e "${RED}✗${NC} Application directory ownership is incorrect (should be proenergia)"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
    fi
fi

# Check log directory
if [ -d "/var/log/proenergia" ]; then
    echo -e "${GREEN}✓${NC} Log directory exists"
else
    echo -e "${RED}✗${NC} Log directory missing"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
fi

echo ""
echo "=== Step 5: Checking Web Application ==="
echo ""

# Get domain from nginx config
if [ -f "/etc/nginx/sites-available/proenergia.conf" ]; then
    DOMAIN=$(grep "server_name" /etc/nginx/sites-available/proenergia.conf | head -1 | awk '{print $2}' | sed 's/;//')
    
    if [ "$DOMAIN" != "" ] && [ "$DOMAIN" != "your-domain.com" ]; then
        echo "Testing domain: $DOMAIN"
        
        # Test HTTP redirect
        test_url "http://$DOMAIN" "HTTP to HTTPS redirect"
        
        # Test HTTPS
        test_url "https://$DOMAIN" "HTTPS site"
        
        # Test API endpoint
        test_url "https://$DOMAIN/api/" "API endpoint"
        
        # Test admin interface
        test_url "https://$DOMAIN/admin/" "Admin interface"
    else
        echo -e "${YELLOW}⚠${NC} Domain not configured properly in nginx"
        echo "  Please update domain in nginx configuration"
    fi
else
    echo -e "${RED}✗${NC} Nginx configuration not found"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
fi

echo ""
echo "=== Step 6: Checking Celery Tasks ==="
echo ""

# Check if Celery is processing tasks
if systemctl is-active --quiet proenergia-celery; then
    # Check Celery stats
    CELERY_ACTIVE=$(systemctl status proenergia-celery | grep "Active: active" | wc -l)
    if [ $CELERY_ACTIVE -eq 1 ]; then
        echo -e "${GREEN}✓${NC} Celery worker is active and ready"
    else
        echo -e "${YELLOW}⚠${NC} Celery worker status unclear"
    fi
else
    echo -e "${RED}✗${NC} Celery worker not running"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
fi

echo ""
echo "=== Step 7: Checking Deployment Tools ==="
echo ""

# Check deployment script
if [ -f "/usr/local/bin/deploy-proenergia" ]; then
    echo -e "${GREEN}✓${NC} Deployment script installed"
else
    echo -e "${RED}✗${NC} Deployment script not found"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
fi

# Check webhook secret
if [ -f "/var/www/proenergia/webhook_secret.txt" ]; then
    echo -e "${GREEN}✓${NC} Webhook secret file exists"
    echo "  To view: sudo cat /var/www/proenergia/webhook_secret.txt"
else
    echo -e "${YELLOW}⚠${NC} Webhook secret file not found"
fi

echo ""
echo "=== Step 8: System Resources Check ==="
echo ""

# Check disk space
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -lt 80 ]; then
    echo -e "${GREEN}✓${NC} Disk usage is healthy ($DISK_USAGE%)"
else
    echo -e "${YELLOW}⚠${NC} Disk usage is high ($DISK_USAGE%)"
fi

# Check memory
MEM_AVAILABLE=$(free -m | awk 'NR==2 {print $7}')
MEM_TOTAL=$(free -m | awk 'NR==2 {print $2}')
MEM_PERCENT=$((100 * MEM_AVAILABLE / MEM_TOTAL))
if [ $MEM_PERCENT -gt 20 ]; then
    echo -e "${GREEN}✓${NC} Memory availability is healthy (${MEM_AVAILABLE}MB available)"
else
    echo -e "${YELLOW}⚠${NC} Low memory available (${MEM_AVAILABLE}MB)"
fi

echo ""
echo "========================================================================="
echo "                         VERIFICATION SUMMARY                           "
echo "========================================================================="
echo ""

if [ $FAILED_CHECKS -eq 0 ]; then
    echo -e "${GREEN}All checks passed successfully!${NC}"
    echo ""
    echo "Your ProEnergia deployment is ready to use."
    echo ""
    echo "Next steps:"
    echo "1. Configure GitHub webhook for automated deployment"
    echo "2. Create a Django superuser account:"
    echo "   cd /var/www/proenergia/app"
    echo "   source venv/bin/activate"
    echo "   python manage.py createsuperuser"
    echo ""
    echo "Useful commands:"
    echo "- View application logs: sudo journalctl -u proenergia -f"
    echo "- Deploy updates: sudo deploy-proenergia"
    echo "- Restart application: sudo systemctl restart proenergia"
else
    echo -e "${RED}$FAILED_CHECKS check(s) failed.${NC}"
    echo ""
    echo "Please review the errors above and:"
    echo "1. Check service logs for failed services"
    echo "2. Verify all setup scripts were run in order"
    echo "3. Ensure all prerequisites are met"
    echo ""
    echo "For troubleshooting, check:"
    echo "- Application logs: sudo journalctl -u proenergia -n 100"
    echo "- Nginx error log: sudo tail -f /var/log/nginx/error.log"
    echo "- PostgreSQL log: sudo tail -f /var/log/postgresql/postgresql-16-main.log"
fi

echo ""
echo "========================================================================="

exit $FAILED_CHECKS