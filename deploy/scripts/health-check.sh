#!/bin/bash

# ProEnergia Health Check Script
# Checks if the application is running properly after deployment
# Usage: ./health-check.sh [--wait]

WAIT_MODE=false
if [[ "$1" == "--wait" ]]; then
    WAIT_MODE=true
fi

MAX_RETRIES=10
RETRY_DELAY=2

# Check service status with retries
check_service() {
    local retries=0
    while [ $retries -lt $MAX_RETRIES ]; do
        if systemctl is-active --quiet proenergia; then
            echo "✓ Service is running"
            return 0
        fi
        
        if [ "$WAIT_MODE" = true ]; then
            retries=$((retries + 1))
            if [ $retries -lt $MAX_RETRIES ]; then
                sleep $RETRY_DELAY
            fi
        else
            break
        fi
    done
    
    echo "✗ Service is not running"
    echo "Check logs: journalctl -u proenergia -f"
    return 1
}

# Check HTTP response
check_http() {
    local retries=0
    while [ $retries -lt $MAX_RETRIES ]; do
        if curl -f -s -o /dev/null -w "%{http_code}" http://localhost:8000/admin/ | grep -q "200\|301\|302"; then
            echo "✓ Application is responding"
            return 0
        fi
        
        if [ "$WAIT_MODE" = true ]; then
            retries=$((retries + 1))
            if [ $retries -lt $MAX_RETRIES ]; then
                sleep $RETRY_DELAY
            fi
        else
            break
        fi
    done
    
    echo "✗ Application is not responding"
    echo "Check application logs: journalctl -u proenergia -f"
    return 1
}

# Run checks
echo "Running health checks..."

SERVICE_OK=false
HTTP_OK=false

if check_service; then
    SERVICE_OK=true
fi

if check_http; then
    HTTP_OK=true
fi

# Exit with appropriate code
if [ "$SERVICE_OK" = true ] && [ "$HTTP_OK" = true ]; then
    echo "Health check passed"
    exit 0
else
    echo "Health check failed"
    exit 1
fi