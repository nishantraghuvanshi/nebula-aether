#!/bin/bash

# Aether GPU Telemetry and Scheduling System - Stop Script
# This script stops all Aether services and cleans up

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}🛑 Stopping Aether Services${NC}"
echo -e "${BLUE}===========================${NC}"
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

# Check if PID file exists
if [ -f "$PROJECT_ROOT/aether.pids" ]; then
    print_info "Reading process IDs from aether.pids..."
    source "$PROJECT_ROOT/aether.pids"
    
    # Stop services in reverse order
    if [ ! -z "$DASHBOARD_PID" ] && kill -0 "$DASHBOARD_PID" 2>/dev/null; then
        print_info "Stopping Dashboard (PID: $DASHBOARD_PID)..."
        kill "$DASHBOARD_PID" 2>/dev/null || true
        print_status "Dashboard stopped"
    fi
    
    if [ ! -z "$ORCHESTRATOR_PID" ] && kill -0 "$ORCHESTRATOR_PID" 2>/dev/null; then
        print_info "Stopping Orchestrator (PID: $ORCHESTRATOR_PID)..."
        kill "$ORCHESTRATOR_PID" 2>/dev/null || true
        print_status "Orchestrator stopped"
    fi
    
    if [ ! -z "$AGENT_PID" ] && kill -0 "$AGENT_PID" 2>/dev/null; then
        print_info "Stopping Agent (PID: $AGENT_PID)..."
        kill "$AGENT_PID" 2>/dev/null || true
        print_status "Agent stopped"
    fi
    
    if [ ! -z "$AI_CORE_PID" ] && kill -0 "$AI_CORE_PID" 2>/dev/null; then
        print_info "Stopping AI Core (PID: $AI_CORE_PID)..."
        kill "$AI_CORE_PID" 2>/dev/null || true
        print_status "AI Core stopped"
    fi
    
    # Remove PID file
    rm -f "$PROJECT_ROOT/aether.pids"
    print_status "Process ID file removed"
else
    print_warning "No PID file found. Attempting to stop services by process name..."
    
    # Stop by process name as fallback
    pkill -f "uvicorn main:app" 2>/dev/null || true
    pkill -f "cargo run" 2>/dev/null || true
    pkill -f "./orchestrator" 2>/dev/null || true
    pkill -f "npm run dev" 2>/dev/null || true
    
    print_status "Services stopped by process name"
fi

# Stop Docker containers
print_info "Stopping Docker containers..."
cd "$PROJECT_ROOT/aether"
docker compose down 2>/dev/null || true
print_status "Docker containers stopped"

# Clean up log files (optional)
read -p "Do you want to clean up log files? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Cleaning up log files..."
    rm -f "$PROJECT_ROOT/aether/apps/ai-core/ai-core.log"
    rm -f "$PROJECT_ROOT/aether/apps/agent/agent.log"
    rm -f "$PROJECT_ROOT/aether/apps/orchestrator/orchestrator.log"
    rm -f "$PROJECT_ROOT/aether/dashboard.log"
    print_status "Log files cleaned up"
fi

echo ""
print_status "All Aether services stopped successfully!"
echo -e "${BLUE}To restart:${NC} ./setup.sh"
