#!/bin/bash

# Deployment script for Catenary Intelligence Service
# This script handles deployment on the VPS

set -e  # Exit on any error

echo "🚀 Starting deployment of Catenary Intelligence Service..."

# Check if we're in the right directory
if [[ ! -f "docker-compose.yml" ]]; then
    echo "❌ Error: docker-compose.yml not found. Are you in the right directory?"
    exit 1
fi

# Function to check service health
check_health() {
    local url=$1
    local max_attempts=10
    local attempt=1

    echo "🏥 Checking health at $url..."

    while [ $attempt -le $max_attempts ]; do
        if curl -f -s "$url" > /dev/null 2>&1; then
            echo "✅ Health check passed!"
            return 0
        fi

        echo "⏳ Attempt $attempt/$max_attempts failed, waiting 5 seconds..."
        sleep 5
        ((attempt++))
    done

    echo "❌ Health check failed after $max_attempts attempts"
    return 1
}

# Stop existing service
echo "🛑 Stopping existing service..."
docker compose down

# Pull latest code if this is a git repository
if [ -d ".git" ]; then
    echo "📥 Pulling latest code..."
    git pull origin main || git pull origin master || echo "⚠️  Git pull failed, continuing with local changes"
fi

# Build the service
echo "🏗️  Building Docker image..."
docker compose build --no-cache catenary-intelligence

# Start the service
echo "▶️  Starting intelligence service..."
docker compose up -d

# Wait for service to start
echo "⏳ Waiting for service to initialize..."
sleep 15

# Check internal health
if check_health "http://localhost:8003/health"; then
    echo "✅ Internal health check passed"
else
    echo "❌ Internal health check failed"
    docker compose logs catenary-intelligence
    exit 1
fi

# Check external health
if check_health "http://204.44.123.122:8002/health"; then
    echo "✅ External health check passed"
else
    echo "❌ External health check failed"
    docker compose logs catenary-intelligence
    exit 1
fi

echo ""
echo "🎉 Deployment completed successfully!"
echo "🔗 Service URL: http://204.44.123.122:8002"
echo "🏥 Health Check: http://204.44.123.122:8002/health"
echo "📊 View logs: docker compose logs -f catenary-intelligence"
echo ""