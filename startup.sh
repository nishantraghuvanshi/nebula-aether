#!/bin/bash
set -e

echo "🌟 Starting Complete Nebula Aether System..."

# Function to check if Docker daemon is running
check_docker_daemon() {
    docker info >/dev/null 2>&1
}

# Function to start Docker Desktop and wait for it to be ready
start_docker_desktop() {
    echo "🐳 Docker daemon not running. Starting Docker Desktop..."
    open -a Docker

    echo "⏳ Waiting for Docker Desktop to start..."
    local max_wait=60
    local wait_time=0

    while ! check_docker_daemon; do
        if [ $wait_time -ge $max_wait ]; then
            echo "❌ Docker Desktop failed to start within $max_wait seconds"
            echo "💡 Please start Docker Desktop manually and try again"
            exit 1
        fi

        sleep 2
        wait_time=$((wait_time + 2))
        echo "   Still waiting... (${wait_time}s/${max_wait}s)"
    done

    echo "✅ Docker Desktop is ready!"
}

# Check dependencies
echo "🔍 Checking dependencies..."
command -v docker >/dev/null 2>&1 || { echo "❌ Docker not installed"; exit 1; }
command -v ngrok >/dev/null 2>&1 || { echo "❌ Ngrok not installed"; exit 1; }
command -v go >/dev/null 2>&1 || { echo "❌ Go not installed"; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "❌ Node.js/npm not installed"; exit 1; }

# Ensure Docker is running
echo "🐳 Checking Docker daemon..."
if ! check_docker_daemon; then
    start_docker_desktop
else
    echo "✅ Docker daemon is already running"
fi

# Kill existing processes
echo "🧹 Cleaning up existing processes..."
pkill -f "go run" 2>/dev/null || true
pkill -f "npm run dev" 2>/dev/null || true
pkill ngrok 2>/dev/null || true
sleep 2

# Start infrastructure
echo "🏗️ Starting infrastructure..."
docker compose up -d

# Start ngrok
echo "📡 Starting ngrok tunnels..."
ngrok start --all &
sleep 5

# Update URLs
echo "🔄 Updating ngrok URLs..."
./update_ngrok_urls.sh

# Start services
echo "🚀 Starting application services..."
./start_services.sh

echo ""
echo "✅ SYSTEM STARTED SUCCESSFULLY!"
echo "================================"
echo "📊 Dashboard: http://localhost:3000"
echo "🔌 API: http://localhost:8080"
echo "📡 Ngrok Status: http://localhost:4040"
echo ""
echo "🎯 Next Steps:"
echo "   1. git push (to sync ngrok URLs to RunPod)"
echo "   2. On RunPod: git pull && cargo run --release"
echo ""
echo "🛑 To stop everything: pkill -f 'go run' && pkill -f 'npm run dev' && pkill ngrok && docker compose down"