#!/bin/bash

# Aether GPU Telemetry and Scheduling System - Linux Stop Script
# This script stops all Aether services and Docker containers

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}🛑 Stopping Aether GPU Telemetry and Scheduling System (Linux)${NC}"
echo -e "${BLUE}================================================================${NC}"
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

# Function to kill process by PID with grace period
kill_process_gracefully() {
    local pid=$1
    local name=$2
    local timeout=${3:-10}
    
    if [ -z "$pid" ] || [ "$pid" = "0" ]; then
        return 0
    fi
    
    # Check if process exists
    if ! kill -0 "$pid" 2>/dev/null; then
        print_info "$name (PID: $pid) is not running"
        return 0
    fi
    
    print_info "Stopping $name (PID: $pid)..."
    
    # Try graceful shutdown first (SIGTERM)
    kill -TERM "$pid" 2>/dev/null || true
    
    # Wait for graceful shutdown
    local count=0
    while [ $count -lt $timeout ]; do
        if ! kill -0 "$pid" 2>/dev/null; then
            print_status "$name stopped gracefully"
            return 0
        fi
        sleep 1
        ((count++))
    done
    
    # Force kill if still running (SIGKILL)
    if kill -0 "$pid" 2>/dev/null; then
        print_warning "$name didn't stop gracefully, force killing..."
        kill -KILL "$pid" 2>/dev/null || true
        sleep 2
        
        if kill -0 "$pid" 2>/dev/null; then
            print_error "Failed to stop $name (PID: $pid)"
            return 1
        else
            print_status "$name force stopped"
        fi
    fi
}

# Function to kill processes by pattern
kill_processes_by_pattern() {
    local pattern=$1
    local name=$2
    
    print_info "Looking for $name processes..."
    
    # Find PIDs matching the pattern
    local pids=$(pgrep -f "$pattern" 2>/dev/null || true)
    
    if [ -z "$pids" ]; then
        print_info "No $name processes found"
        return 0
    fi
    
    echo "Found $name processes with PIDs: $pids"
    
    # Kill each process
    for pid in $pids; do
        kill_process_gracefully "$pid" "$name"
    done
}

# Step 1: Stop processes using PID file if it exists
print_info "Checking for saved process IDs..."

PID_FILE="$PROJECT_ROOT/aether.pids"
if [ -f "$PID_FILE" ]; then
    print_info "Found PID file: $PID_FILE"
    
    # Source the PID file
    source "$PID_FILE" 2>/dev/null || true
    
    # Stop each service
    if [ -n "$DASHBOARD_PID" ]; then
        kill_process_gracefully "$DASHBOARD_PID" "Dashboard"
    fi
    
    if [ -n "$ORCHESTRATOR_PID" ]; then
        kill_process_gracefully "$ORCHESTRATOR_PID" "Orchestrator"
    fi
    
    if [ -n "$AGENT_PID" ]; then
        kill_process_gracefully "$AGENT_PID" "Agent"
    fi
    
    if [ -n "$AI_CORE_PID" ]; then
        kill_process_gracefully "$AI_CORE_PID" "AI Core"
    fi
    
    # Remove the PID file
    rm -f "$PID_FILE"
    print_status "Removed PID file"
else
    print_warning "No PID file found, will search for processes by pattern"
fi

# Step 2: Kill any remaining processes by pattern
print_info "Searching for any remaining Aether processes..."

# Kill Dashboard (Next.js dev server)
kill_processes_by_pattern "npm.*run.*dev" "Dashboard"
kill_processes_by_pattern "next.*dev" "Next.js Dashboard"

# Kill Orchestrator
kill_processes_by_pattern "./orchestrator" "Orchestrator"
kill_processes_by_pattern "go.*run.*main.go" "Go Orchestrator"

# Kill Agent
kill_processes_by_pattern "./target/release/agent" "Rust Agent"
kill_processes_by_pattern "cargo.*run.*release" "Rust Agent (dev)"

# Kill AI Core
kill_processes_by_pattern "uvicorn.*main:app" "AI Core API"
kill_processes_by_pattern "python.*main.py" "AI Core API"

# Step 3: Stop Docker services
print_info "Stopping Docker containers..."

cd "$PROJECT_ROOT"

# Check if docker-compose.yml exists
if [ -f "docker-compose.yml" ]; then
    if command -v docker &> /dev/null && docker info &> /dev/null 2>&1; then
        print_info "Stopping Docker containers..."
        docker compose down 2>/dev/null || {
            print_warning "docker compose down failed, trying docker-compose..."
            docker-compose down 2>/dev/null || true
        }
        
        # Also stop any containers that might be running from previous sessions
        print_info "Checking for any remaining Aether containers..."
        
        # Stop NATS container
        if docker ps -q -f "name=nats" | grep -q .; then
            print_info "Stopping NATS container..."
            docker stop $(docker ps -q -f "name=nats") 2>/dev/null || true
        fi
        
        # Stop TimescaleDB container
        if docker ps -q -f "name=timescaledb" | grep -q .; then
            print_info "Stopping TimescaleDB container..."
            docker stop $(docker ps -q -f "name=timescaledb") 2>/dev/null || true
        fi
        
        # Stop any containers with "aether" in the name
        local aether_containers=$(docker ps -q -f "name=aether" 2>/dev/null || true)
        if [ -n "$aether_containers" ]; then
            print_info "Stopping additional Aether containers..."
            docker stop $aether_containers 2>/dev/null || true
        fi
        
        print_status "Docker containers stopped"
    else
        print_warning "Docker is not running or not accessible"
    fi
else
    print_warning "docker-compose.yml not found"
fi

# Step 4: Clean up any remaining ports
print_info "Checking for services on common Aether ports..."

# Function to kill process using a specific port
kill_port_process() {
    local port=$1
    local service_name=$2
    
    local pid=$(lsof -ti:$port 2>/dev/null || true)
    if [ -n "$pid" ]; then
        print_warning "$service_name still running on port $port (PID: $pid), stopping it..."
        kill_process_gracefully "$pid" "$service_name on port $port"
    fi
}

# Check common Aether ports
kill_port_process "3000" "Dashboard"
kill_port_process "8000" "AI Core API"
kill_port_process "8080" "Orchestrator"
kill_port_process "4222" "NATS"
kill_port_process "5432" "TimescaleDB"

# Step 5: Clean up log files (optional)
print_info "Cleaning up log files..."

# Create logs backup if they exist and are not empty
if ls "$PROJECT_ROOT"/*.log 1> /dev/null 2>&1; then
    BACKUP_DIR="$PROJECT_ROOT/logs_backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    for log_file in "$PROJECT_ROOT"/*.log; do
        if [ -f "$log_file" ] && [ -s "$log_file" ]; then
            cp "$log_file" "$BACKUP_DIR/"
        fi
    done
    
    if [ "$(ls -A $BACKUP_DIR 2>/dev/null)" ]; then
        print_status "Log files backed up to: $BACKUP_DIR"
    else
        rmdir "$BACKUP_DIR"
    fi
fi

# Clean up service-specific log files
for log_dir in "apps/ai-core" "apps/agent" "apps/orchestrator"; do
    if [ -d "$PROJECT_ROOT/$log_dir" ]; then
        find "$PROJECT_ROOT/$log_dir" -name "*.log" -type f -exec rm -f {} \; 2>/dev/null || true
    fi
done

# Remove main log files
rm -f "$PROJECT_ROOT"/*.log 2>/dev/null || true

print_status "Log files cleaned up"

# Step 6: Final verification
print_info "Verifying all services are stopped..."

# Check if any Aether processes are still running
remaining_processes=$(pgrep -f "aether|orchestrator|uvicorn.*main|npm.*run.*dev|target/release/agent" 2>/dev/null || true)

if [ -n "$remaining_processes" ]; then
    print_warning "Some processes may still be running:"
    ps -p $remaining_processes -o pid,ppid,cmd --no-headers 2>/dev/null || true
    echo ""
    print_warning "You may need to manually kill these processes:"
    echo "kill -9 $remaining_processes"
else
    print_status "All Aether processes stopped"
fi

# Check Docker containers
if command -v docker &> /dev/null && docker info &> /dev/null 2>&1; then
    running_containers=$(docker ps -q -f "name=nats" -f "name=timescaledb" -f "name=aether" 2>/dev/null || true)
    if [ -n "$running_containers" ]; then
        print_warning "Some Docker containers may still be running:"
        docker ps --filter "name=nats" --filter "name=timescaledb" --filter "name=aether" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || true
    else
        print_status "All Docker containers stopped"
    fi
fi

# Final status
echo ""
echo -e "${GREEN}🎯 Aether Stop Script Complete!${NC}"
echo -e "${GREEN}================================${NC}"
echo ""
echo -e "${BLUE}Services Stopped:${NC}"
echo "  • Dashboard (Next.js)"
echo "  • AI Core API (FastAPI/Uvicorn)" 
echo "  • Orchestrator (Go)"
echo "  • Agent (Rust)"
echo "  • NATS (Docker)"
echo "  • TimescaleDB (Docker)"
echo ""
echo -e "${BLUE}Actions Taken:${NC}"
echo "  • Stopped all service processes gracefully"
echo "  • Stopped Docker containers"
echo "  • Freed up network ports"
echo "  • Cleaned up log files (with backup)"
echo "  • Removed PID tracking file"
echo ""

if [ -n "$remaining_processes" ] || [ -n "$running_containers" ]; then
    echo -e "${YELLOW}⚠️  Some services may require manual cleanup (see warnings above)${NC}"
else
    echo -e "${GREEN}✅ All services stopped cleanly!${NC}"
fi

echo ""
echo -e "${BLUE}To restart the system:${NC} ./setup_linux.sh"
echo ""