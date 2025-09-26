#!/bin/bash

echo "🛑 Stopping Nebula Aether System..."

# Stop application processes
echo "🧹 Stopping application services..."
pkill -f "go run.*orchestrator" 2>/dev/null || true
pkill -f "npm run dev" 2>/dev/null || true

# Stop ngrok tunnels
echo "📡 Stopping ngrok tunnels..."
pkill ngrok 2>/dev/null || true

# Force kill by port (backup cleanup)
echo "🔧 Cleaning up ports..."
lsof -ti:8080 2>/dev/null | xargs kill -9 2>/dev/null || true  # Orchestrator
lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true  # Dashboard
lsof -ti:4040 2>/dev/null | xargs kill -9 2>/dev/null || true  # Ngrok web UI
lsof -ti:4222 2>/dev/null | xargs kill -9 2>/dev/null || true  # NATS
lsof -ti:5432 2>/dev/null | xargs kill -9 2>/dev/null || true  # TimescaleDB

# Stop Docker services
echo "🐳 Stopping Docker services..."
docker compose down --remove-orphans

# Clean up PID files
rm -f .orchestrator.pid .dashboard.pid

echo ""
echo "✅ SYSTEM STOPPED SUCCESSFULLY!"
echo "==============================="
echo "🔍 Verify with: docker compose ps"
echo "🔍 Check ports: lsof -i :3000,:8080,:4222"
echo ""
echo "🚀 To restart: ./startup.sh"


