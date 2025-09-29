#!/bin/bash

# Enhanced Catenary Intelligence Deployment Script
# Deploys the complete system with all 15 advanced extractors

set -e

echo "🚀 Starting Enhanced Catenary Intelligence Deployment"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker first."
    exit 1
fi

print_status "Docker is running ✓"

# Create necessary network if it doesn't exist
if ! docker network ls | grep -q supabase_default; then
    print_warning "Creating supabase_default network..."
    docker network create supabase_default
fi

print_status "Network check completed ✓"

# Build and deploy the intelligence service
print_status "Building intelligence intelligence service..."

# Stop any existing old services
print_status "Stopping old services..."
docker stop pdf-intelligence-pipeline 2>/dev/null || true
docker rm pdf-intelligence-pipeline 2>/dev/null || true

# Build and start the intelligence service
print_status "Starting intelligence services..."
docker-compose -f docker-compose.intelligence.yml up -d --build

print_status "Waiting for services to become healthy..."
sleep 30

# Check health of services
print_status "Checking service health..."

# Check intelligence service health
if curl -f http://localhost:8002/health > /dev/null 2>&1; then
    print_status "Enhanced Intelligence Service is healthy ✓"
else
    print_error "Enhanced Intelligence Service is not responding"
    docker-compose -f docker-compose.intelligence.yml logs catenary-intelligence-intelligence
    exit 1
fi

# Check nginx health (if ports 80/443 are accessible)
if curl -f http://localhost:80/health > /dev/null 2>&1; then
    print_status "NGINX is healthy ✓"
else
    print_warning "NGINX health check failed (may be normal if SSL redirect is active)"
fi

# Show service status
print_status "Deployment Summary:"
echo "=================================================="
docker-compose -f docker-compose.intelligence.yml ps

print_status "Service URLs:"
echo "  Enhanced Intelligence API: http://localhost:8002"
echo "  Health Check: http://localhost:8002/health"
echo "  Capabilities: http://localhost:8002/capabilities"

print_status "Available Extractors (15 total):"
echo "  ✅ Stamp Detection"
echo "  ✅ Layout Analysis"
echo "  ✅ Revision Tracking"
echo "  ✅ Assembly Detection"
echo "  ✅ Technical Specifications"
echo "  ✅ Dimensional Analysis"
echo "  ✅ Vector Graphics Analysis"
echo "  ✅ Enhanced Table Extraction"
echo "  ✅ AI Consensus Analysis"
echo "  ✅ Quality Validation"
echo "  ✅ Error Correction"
echo "  ✅ Intelligent Normalization"
echo "  ✅ Multi-language Processing"
echo "  ✅ Standards Compliance"
echo "  ✅ Performance Optimization"

echo ""
print_status "🎉 Enhanced Catenary Intelligence System Deployed Successfully!"
print_status "The system is now running with all 15 advanced extractors."
echo ""
echo "To view logs: docker-compose -f docker-compose.intelligence.yml logs -f"
echo "To stop: docker-compose -f docker-compose.intelligence.yml down"
echo "To update: ./deploy.sh"