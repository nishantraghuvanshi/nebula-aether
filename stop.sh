#!/bin/bash

# Aether GPU Telemetry and Scheduling System - Stop Script
# This script stops all Aether services and cleans up (Linux/macOS compatible)

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

# Function to kill process gracefully
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

# Check if PID file exists
if [ -f "$PROJECT_ROOT/aether.pids" ]; then
    print_info "Reading process IDs from aether.pids..."
    source "$PROJECT_ROOT/aether.pids"
    
    # Stop services in reverse order
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
    
    # Remove PID file
    rm -f "$PROJECT_ROOT/aether.pids"
    print_status "Process ID file removed"
else
    print_warning "No PID file found. Attempting to stop services by process name..."
    
    # Stop by process name as fallback - improved pattern matching
    print_info "Stopping AI Core..."
    pkill -f "uvicorn.*main:app" 2>/dev/null || true
    pkill -f "python.*main.py" 2>/dev/null || true
    
    print_info "Stopping Agent..."
    pkill -f "target/release/agent" 2>/dev/null || true
    pkill -f "cargo.*run.*release" 2>/dev/null || true
    
    print_info "Stopping Orchestrator..."
    pkill -f "./orchestrator" 2>/dev/null || true
    pkill -f "go.*run.*main.go" 2>/dev/null || true
    
    print_info "Stopping Dashboard..."
    pkill -f "npm.*run.*dev" 2>/dev/null || true
    pkill -f "next.*dev" 2>/dev/null || true
    
    print_status "Services stopped by process name"
fi

# Stop Docker containers
print_info "Stopping Docker containers..."
cd "$PROJECT_ROOT"

if command -v docker &> /dev/null && docker info &> /dev/null 2>&1; then
    docker compose down 2>/dev/null || {
        print_warning "docker compose down failed, trying docker-compose..."
        docker-compose down 2>/dev/null || true
    }
    print_status "Docker containers stopped"
else
    print_warning "Docker is not running or not accessible"
fi

# Check for services on common ports and stop them
print_info "Checking for services on common Aether ports..."

# Function to kill process using a specific port (if lsof is available)
if command -v lsof &> /dev/null; then
    for port in 3000 8000 8080 4222 5432; do
        pid=$(lsof -ti:$port 2>/dev/null || true)
        if [ -n "$pid" ]; then
            print_warning "Process still running on port $port (PID: $pid), stopping it..."
            kill_process_gracefully "$pid" "Service on port $port"
        fi
    done
fi

# Clean up log files (optional)
print_info "Log file cleanup options:"
echo "  1. Keep all logs"
echo "  2. Clean all logs" 
echo "  3. Backup and clean logs"
read -p "Choose option (1-3) [1]: " -n 1 -r
echo ""

case ${REPLY:-1} in
    2)
        print_info "Cleaning up log files..."
        rm -f "$PROJECT_ROOT"/*.log
        find "$PROJECT_ROOT" -name "*.log" -type f -delete 2>/dev/null || true
        print_status "Log files cleaned up"
        ;;
    3)
        print_info "Backing up and cleaning log files..."
        BACKUP_DIR="$PROJECT_ROOT/logs_backup_$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP_DIR"
        
        # Backup main logs
        for log_file in "$PROJECT_ROOT"/*.log; do
            if [ -f "$log_file" ]; then
                cp "$log_file" "$BACKUP_DIR/" 2>/dev/null || true
            fi
        done
        
        # Backup service logs
        find "$PROJECT_ROOT" -name "*.log" -type f -exec cp {} "$BACKUP_DIR/" \; 2>/dev/null || true
        
        # Clean up originals
        rm -f "$PROJECT_ROOT"/*.log
        find "$PROJECT_ROOT" -name "*.log" -type f -delete 2>/dev/null || true
        
        if [ "$(ls -A $BACKUP_DIR 2>/dev/null)" ]; then
            print_status "Logs backed up to: $BACKUP_DIR"
        else
            rmdir "$BACKUP_DIR"
            print_status "No logs to backup"
        fi
        ;;
    *)
        print_info "Keeping all log files"
        ;;
esac

echo ""
print_status "All Aether services stopped successfully!"

# Detect OS for restart instruction
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo -e "${BLUE}To restart:${NC} ./setup_linux.sh"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo -e "${BLUE}To restart:${NC} ./setup.sh"
else
    echo -e "${BLUE}To restart:${NC} ./setup_linux.sh or ./setup.sh"
fi

echo ""
