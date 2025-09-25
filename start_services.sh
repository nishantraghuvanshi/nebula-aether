#!/bin/bash
set -e

echo "🚀 Starting Nebula Aether services..."

# Kill any existing processes first
echo "🧹 Cleaning up existing processes..."
pkill -f "go run.*orchestrator" 2>/dev/null || true
pkill -f "npm run dev" 2>/dev/null || true

# Start orchestrator
echo "Starting orchestrator..."
cd apps/orchestrator
go run . &
ORCHESTRATOR_PID=$!
cd ../..

# Start dashboard
echo "Starting dashboard..."
cd apps/dashboard
npm run dev &
DASHBOARD_PID=$!
cd ../..

# Save PIDs for later cleanup
echo $ORCHESTRATOR_PID > .orchestrator.pid
echo $DASHBOARD_PID > .dashboard.pid

sleep 3

echo "✅ Services started!"
echo "📊 Dashboard: http://localhost:3000"
echo "🔌 Orchestrator API: http://localhost:8080"
echo "📄 PIDs saved to .orchestrator.pid and .dashboard.pid"
echo ""
echo "💡 To stop services: pkill -f 'go run' && pkill -f 'npm run dev'"

