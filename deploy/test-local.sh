#!/bin/bash

# Automated test script for ProEnergia deployment in Docker container
# This script runs inside the container to test the deployment process

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  ProEnergia Deployment Test Script    ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Configuration for testing
TEST_DOMAIN="localhost"
TEST_EMAIL="admin@localhost"
REPO_URL="https://github.com/developmentseed/moz-proenergia-backend.git"

# Function to check if last command succeeded
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ $1 completed successfully${NC}"
    else
        echo -e "${RED}✗ $1 failed${NC}"
        exit 1
    fi
}

# Function to print section headers
print_section() {
    echo ""
    echo -e "${YELLOW}=== $1 ===${NC}"
    echo ""
}

print_section "Step 0: Cleaning up any previous test"
cd /root
rm -rf moz-proenergia-backend
check_status "Cleanup"

print_section "Step 1: Cloning repository"
git clone $REPO_URL
check_status "Repository clone"

cd moz-proenergia-backend/deploy/scripts
chmod +x *.sh
check_status "Making scripts executable"

print_section "Step 2: Running 00_setup_system.sh"
./00_setup_system.sh
check_status "System setup"

print_section "Step 3: Running 01_setup_infrastructure.sh"
echo "Using domain: $TEST_DOMAIN"
./01_setup_infrastructure.sh $TEST_DOMAIN > /tmp/infrastructure_output.txt 2>&1
cat /tmp/infrastructure_output.txt
check_status "Infrastructure setup"

# Extract and save credentials
echo ""
echo -e "${BLUE}Extracting credentials...${NC}"
grep -A 20 "IMPORTANT: Save these credentials" /tmp/infrastructure_output.txt || true

print_section "Step 4: Running 02_setup_application.sh"
sudo -u proenergia ./02_setup_application.sh
check_status "Application setup"

print_section "Step 5: Modifying 03_setup_services.sh for local testing"
# Create a modified version that skips SSL
cp 03_setup_services.sh 03_setup_services_local.sh

# Comment out SSL setup for local testing
sed -i 's/^certbot /#certbot /' 03_setup_services_local.sh
sed -i 's/^systemctl enable certbot/#systemctl enable certbot/' 03_setup_services_local.sh
sed -i 's/^systemctl start certbot/#systemctl start certbot/' 03_setup_services_local.sh

echo "Running modified services setup (SSL disabled for local testing)..."
./03_setup_services_local.sh $TEST_DOMAIN $TEST_EMAIL
check_status "Services setup"

print_section "Step 6: Running verification"
./04_verify_setup.sh || true  # Don't fail on verification issues

print_section "Test Summary"

echo "Checking critical services:"
echo ""

# Check services
systemctl is-active --quiet postgresql && echo -e "${GREEN}✓ PostgreSQL running${NC}" || echo -e "${RED}✗ PostgreSQL not running${NC}"
systemctl is-active --quiet rabbitmq-server && echo -e "${GREEN}✓ RabbitMQ running${NC}" || echo -e "${RED}✗ RabbitMQ not running${NC}"
systemctl is-active --quiet nginx && echo -e "${GREEN}✓ Nginx running${NC}" || echo -e "${RED}✗ Nginx not running${NC}"
systemctl is-active --quiet proenergia && echo -e "${GREEN}✓ ProEnergia app running${NC}" || echo -e "${RED}✗ ProEnergia app not running${NC}"
systemctl is-active --quiet proenergia-celery && echo -e "${GREEN}✓ Celery running${NC}" || echo -e "${RED}✗ Celery not running${NC}"

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}         Test Complete!                 ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Application should be accessible at:"
echo "  - http://localhost:8080 (from host machine)"
echo "  - http://localhost (from inside container)"
echo ""
echo "To create a superuser:"
echo "  cd /var/www/proenergia/app"
echo "  source venv/bin/activate"
echo "  python manage.py createsuperuser"
echo ""
echo "To check logs:"
echo "  journalctl -u proenergia -f"
echo ""
echo "To test the API:"
echo "  curl http://localhost/api/"
echo ""

# Optional: Test if the app is responding
print_section "Testing HTTP endpoints"
sleep 5  # Give services time to start

echo "Testing main page..."
curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" http://localhost/ || echo "Failed to connect"

echo "Testing API endpoint..."
curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" http://localhost/api/ || echo "Failed to connect"

echo "Testing admin interface..."
curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" http://localhost/admin/ || echo "Failed to connect"

echo ""
echo -e "${GREEN}Deployment test script finished!${NC}"