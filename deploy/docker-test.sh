#!/bin/bash

# Helper script to build and run Docker container for testing ProEnergia deployment

set -e

echo "=== ProEnergia Docker Test Environment ==="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Container name
CONTAINER_NAME="proenergia-test"
IMAGE_NAME="proenergia-test"

# Function to stop and remove existing container
cleanup_container() {
    echo "Checking for existing container..."
    if docker ps -a | grep -q $CONTAINER_NAME; then
        echo "Stopping and removing existing container..."
        docker stop $CONTAINER_NAME 2>/dev/null || true
        docker rm $CONTAINER_NAME 2>/dev/null || true
    fi
}

# Parse command line arguments
case "$1" in
    build)
        echo "Building Docker image..."
        docker build -f Dockerfile.test -t $IMAGE_NAME .
        echo -e "${GREEN}✓ Image built successfully${NC}"
        ;;
    
    run)
        cleanup_container
        echo "Starting container..."
        docker run -d \
            --privileged \
            --name $CONTAINER_NAME \
            -p 8080:80 \
            -p 8443:443 \
            -p 8000:8000 \
            --cgroupns=host \
            -v /sys/fs/cgroup:/sys/fs/cgroup:rw \
            $IMAGE_NAME
        
        echo -e "${GREEN}✓ Container started${NC}"
        echo ""
        echo "Container is running with:"
        echo "  Name: $CONTAINER_NAME"
        echo "  HTTP: http://localhost:8080"
        echo "  HTTPS: https://localhost:8443"
        echo "  Django: http://localhost:8000"
        echo ""
        echo -e "${YELLOW}Waiting for systemd to initialize...${NC}"
        sleep 5
        echo ""
        echo "To enter the container, run:"
        echo "  docker exec -it $CONTAINER_NAME bash"
        echo ""
        echo "Then run the test script:"
        echo "  /root/test-local.sh"
        ;;
    
    exec)
        echo "Entering container..."
        docker exec -it $CONTAINER_NAME bash
        ;;
    
    logs)
        docker logs -f $CONTAINER_NAME
        ;;
    
    stop)
        echo "Stopping container..."
        docker stop $CONTAINER_NAME
        echo -e "${GREEN}✓ Container stopped${NC}"
        ;;
    
    clean)
        cleanup_container
        echo -e "${GREEN}✓ Container removed${NC}"
        ;;
    
    reset)
        cleanup_container
        echo "Rebuilding and starting fresh container..."
        docker build -f Dockerfile.test -t $IMAGE_NAME .
        docker run -d \
            --privileged \
            --name $CONTAINER_NAME \
            -p 8080:80 \
            -p 8443:443 \
            -p 8000:8000 \
            --cgroupns=host \
            -v /sys/fs/cgroup:/sys/fs/cgroup:rw \
            $IMAGE_NAME
        sleep 5
        echo -e "${GREEN}✓ Fresh container ready${NC}"
        echo "Run: docker exec -it $CONTAINER_NAME bash"
        ;;
    
    test)
        echo "Running automated test..."
        # Copy test script into container
        docker cp test-local.sh $CONTAINER_NAME:/root/test-local.sh
        docker exec $CONTAINER_NAME chmod +x /root/test-local.sh
        
        # Run test script
        docker exec -it $CONTAINER_NAME /root/test-local.sh
        ;;
    
    *)
        echo "Usage: $0 {build|run|exec|logs|stop|clean|reset|test}"
        echo ""
        echo "Commands:"
        echo "  build  - Build the Docker image"
        echo "  run    - Run the container (removes existing if present)"
        echo "  exec   - Open bash shell in running container"
        echo "  logs   - Show container logs"
        echo "  stop   - Stop the container"
        echo "  clean  - Stop and remove container"
        echo "  reset  - Clean, rebuild, and start fresh"
        echo "  test   - Run automated deployment test"
        echo ""
        echo "Typical workflow:"
        echo "  1. $0 build    # Build image"
        echo "  2. $0 run      # Start container"
        echo "  3. $0 exec     # Enter container"
        echo "  4. Run deployment scripts manually or use: $0 test"
        exit 1
        ;;
esac