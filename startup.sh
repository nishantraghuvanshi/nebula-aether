#!/bin/bash
set -e

echo "🌟 Starting Complete Nebula Aether System..."

# Check dependencies
echo "🔍 Checking dependencies..."
command -v docker >/dev/null 2>&1 || { echo "❌ Docker not installed"; exit 1; }
command -v ngrok >/dev/null 2>&1 || { echo "❌ Ngrok not installed"; exit 1; }
command -v go >/dev/null 2>&1 || { echo "❌ Go not installed"; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "❌ Node.js/npm not installed"; exit 1; }

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