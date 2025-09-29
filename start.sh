#!/bin/bash

echo "🐍 Starting Python Document Analysis Service..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "📋 Installing dependencies..."
pip install -r requirements.txt

# Start the service
echo "🚀 Starting analysis service on port 8002..."
echo ""
echo "📍 Service will be available at: http://localhost:8002"
echo "📍 Health check: http://localhost:8002/health"
echo "📍 API docs: http://localhost:8002/docs"
echo ""

python main.py