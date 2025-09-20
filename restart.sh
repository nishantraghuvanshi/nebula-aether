#!/bin/bash

# Aether GPU Telemetry and Scheduling System - Restart Script
# This script restarts all Aether services for users who have already run setup.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AETHER_DIR="$PROJECT_ROOT/aether"

echo -e "${BLUE}🔄 Restarting Aether Services${NC}"
echo -e "${BLUE}============================${NC}"
echo ""

# Function to print status messages
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check if setup has been run before
if [ ! -f "$PROJECT_ROOT/aether.pids" ] && [ ! -d "$AETHER_DIR" ]; then
    print_error "Aether setup not found. Please run ./setup.sh first."
    exit 1
fi

# Step 1: Stop any existing services
print_info "Stopping any existing services..."

# Kill processes by PID file if it exists
if [ -f "$PROJECT_ROOT/aether.pids" ]; then
    source "$PROJECT_ROOT/aether.pids"
    
    if [ ! -z "$DASHBOARD_PID" ] && kill -0 "$DASHBOARD_PID" 2>/dev/null; then
        kill "$DASHBOARD_PID" 2>/dev/null || true
    fi
    
    if [ ! -z "$ORCHESTRATOR_PID" ] && kill -0 "$ORCHESTRATOR_PID" 2>/dev/null; then
        kill "$ORCHESTRATOR_PID" 2>/dev/null || true
    fi
    
    if [ ! -z "$AGENT_PID" ] && kill -0 "$AGENT_PID" 2>/dev/null; then
        kill "$AGENT_PID" 2>/dev/null || true
    fi
    
    if [ ! -z "$AI_CORE_PID" ] && kill -0 "$AI_CORE_PID" 2>/dev/null; then
        kill "$AI_CORE_PID" 2>/dev/null || true
    fi
    
    rm -f "$PROJECT_ROOT/aether.pids"
fi

# Kill by process name as fallback
pkill -f "uvicorn main:app" 2>/dev/null || true
pkill -f "cargo run" 2>/dev/null || true
pkill -f "./orchestrator" 2>/dev/null || true
pkill -f "npm run dev" 2>/dev/null || true

print_status "Existing services stopped"

# Step 2: Start Infrastructure
print_info "Starting infrastructure services..."

cd "$AETHER_DIR"

# Start Docker containers
docker compose up -d

# Wait for services to be ready
print_info "Waiting for services to start..."
sleep 5

# Verify services are running
if ! docker ps | grep -q "nats"; then
    print_error "NATS container failed to start"
    exit 1
fi

if ! docker ps | grep -q "timescaledb"; then
    print_error "TimescaleDB container failed to start"
    exit 1
fi

print_status "Infrastructure services started"

# Step 3: Start All Services
print_info "Starting all services..."

# Start AI Core in background
print_info "Starting AI Core API..."
cd "$AETHER_DIR/apps/ai-core"
eval "$(conda shell.bash hook)"
conda activate aether-ai
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > ai-core.log 2>&1 &
AI_CORE_PID=$!

# Wait for AI Core to start
sleep 3

# Start Rust Agent in background
print_info "Starting Rust Telemetry Agent..."
cd "$AETHER_DIR/apps/agent"
nohup cargo run --release > agent.log 2>&1 &
AGENT_PID=$!

# Wait for agent to start
sleep 3

# Start Go Orchestrator in background
print_info "Starting Go Orchestrator..."
cd "$AETHER_DIR/apps/orchestrator"
nohup ./orchestrator > orchestrator.log 2>&1 &
ORCHESTRATOR_PID=$!

# Wait for orchestrator to start
sleep 3

# Start Dashboard in background
print_info "Starting Dashboard..."
cd "$AETHER_DIR"
nohup npm run dev > dashboard.log 2>&1 &
DASHBOARD_PID=$!

# Wait for dashboard to start
sleep 5

print_status "All services started"

# Step 4: Save Process IDs
print_info "Saving process information..."

cat > "$PROJECT_ROOT/aether.pids" << EOF
# Aether Process IDs - Generated $(date)
AI_CORE_PID=$AI_CORE_PID
AGENT_PID=$AGENT_PID
ORCHESTRATOR_PID=$ORCHESTRATOR_PID
DASHBOARD_PID=$DASHBOARD_PID
EOF

# Step 5: Verification
print_info "Verifying services..."

# Check if services are responding
services_ok=true

# Check AI Core
if ! curl -s http://localhost:8000/docs > /dev/null; then
    print_warning "AI Core API not responding on port 8000"
    services_ok=false
else
    print_status "AI Core API: http://localhost:8000"
fi

# Check Orchestrator
if ! curl -s http://localhost:8080/submit > /dev/null 2>&1; then
    print_warning "Orchestrator API not responding on port 8080"
    services_ok=false
else
    print_status "Orchestrator API: http://localhost:8080"
fi

# Check Dashboard
if ! curl -s http://localhost:3000 > /dev/null; then
    print_warning "Dashboard not responding on port 3000"
    services_ok=false
else
    print_status "Dashboard: http://localhost:3000"
fi

# Step 6: Final Status
echo ""
echo -e "${GREEN}🎉 Aether Services Restarted!${NC}"
echo -e "${GREEN}============================${NC}"
echo ""
echo -e "${BLUE}Services Running:${NC}"
echo "  • AI Core API:     http://localhost:8000"
echo "  • Orchestrator:    http://localhost:8080"
echo "  • Dashboard:       http://localhost:3000"
echo "  • NATS:            nats://localhost:4222"
echo "  • TimescaleDB:     postgres://aether:aether@localhost:5432/aether"
echo ""
echo -e "${BLUE}Process IDs saved to:${NC} aether.pids"
echo ""
echo -e "${BLUE}Logs:${NC}"
echo "  • AI Core:         aether/apps/ai-core/ai-core.log"
echo "  • Agent:           aether/apps/agent/agent.log"
echo "  • Orchestrator:    aether/apps/orchestrator/orchestrator.log"
echo "  • Dashboard:       aether/dashboard.log"
echo ""
echo -e "${YELLOW}To stop all services:${NC} ./stop.sh"
echo -e "${YELLOW}To test the system:${NC} ./test.sh"
echo ""

if [ "$services_ok" = true ]; then
    print_status "All services are running correctly!"
    echo -e "${GREEN}🚀 Aether is ready to use!${NC}"
else
    print_warning "Some services may not be running correctly. Check the logs above."
fi
