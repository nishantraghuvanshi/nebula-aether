#!/bin/bash

# Aether GPU Telemetry and Scheduling System - Complete Setup Script (Linux Version)

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AETHER_DIR="$PROJECT_ROOT"

echo -e "${BLUE}🚀 Aether GPU Telemetry and Scheduling System Setup${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Function to print status messages
print_status() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    print_error "This setup script is designed for Linux. Please adapt for your OS."
    exit 1
fi

# Check for required tools
print_info "Checking system requirements..."

# Check Docker
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Install Docker: https://docs.docker.com/engine/install/"
    exit 1
fi

# Check if Docker daemon is running
# Check Docker daemon
if ! docker info &> /dev/null; then
    print_error "Docker is not running. Start it with: sudo systemctl start docker"
    exit 1
fi


# Check Rust
if ! command -v cargo &> /dev/null; then
    print_warning "Rust is not installed. Installing via rustup..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source ~/.cargo/env
fi

# Check Go
if ! command -v go &> /dev/null; then
    print_error "Go is not installed. Please install Go: https://golang.org/dl/"
    exit 1
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    print_error "Node.js is not installed. Install LTS: https://nodejs.org/"
    exit 1
fi

# Check Conda
if ! command -v conda &> /dev/null; then
    print_error "Conda is not installed. Install Miniconda: https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

print_status "All system requirements met"

# ---------------- Infrastructure ----------------
print_info "Starting infrastructure services (NATS, TimescaleDB)..."

cd "$AETHER_DIR"

docker compose down 2>/dev/null || true
docker compose up -d

print_info "Waiting for services to start..."
sleep 10

if ! docker ps | grep -q "nats"; then
    print_error "NATS container failed to start"
    exit 1
fi

if ! docker ps | grep -q "timescaledb"; then
    print_error "TimescaleDB container failed to start"
    exit 1
fi

print_status "Infrastructure services started"

# ---------------- Database ----------------
print_info "Setting up database schema..."
sleep 5

docker compose exec -T timescaledb psql -U aether -d postgres -c "CREATE DATABASE aether;" 2>/dev/null || true

docker compose exec -T timescaledb psql -U aether -d aether -c "
CREATE TABLE IF NOT EXISTS gpu_telemetry (
    time TIMESTAMPTZ NOT NULL,
    gpu_name TEXT,
    temperature_c INTEGER,
    memory_used_mb BIGINT,
    memory_total_mb BIGINT,
    utilization_gpu INTEGER,
    utilization_memory_controller INTEGER,
    clock_gpu_mhz INTEGER,
    clock_mem_mhz INTEGER,
    power_draw_w INTEGER,
    performance_state TEXT,
    throttling_reasons TEXT,
    gpu_id TEXT
);" 2>/dev/null || true

docker compose exec -T timescaledb psql -U aether -d aether -c "SELECT create_hypertable('gpu_telemetry', 'time', if_not_exists => TRUE);" 2>/dev/null || true

print_status "Database schema ready"

# ---------------- AI Core ----------------
print_info "Setting up AI Core (Python)..."

cd "$AETHER_DIR/apps/ai-core"

if ! conda env list | grep -q "aether-ai"; then
    print_info "Creating conda environment 'aether-ai'..."
    conda create -n aether-ai python=3.9 -y
fi

eval "$(conda shell.bash hook)"
conda activate aether-ai

pip install -r requirements.txt
python simulator.py
python train.py

print_status "AI Core ready"

# ---------------- Rust Agent ----------------
print_info "Setting up Rust Agent..."

cd "$AETHER_DIR/apps/agent"
# Build without NVML by default on Linux to avoid missing library issues
cargo build --release --no-default-features

print_status "Rust Agent ready"

# ---------------- Go Orchestrator ----------------
print_info "Setting up Go Orchestrator..."

cd "$AETHER_DIR/apps/orchestrator"
go mod tidy
go build -o orchestrator main.go

print_status "Go Orchestrator ready"

# ---------------- Dashboard ----------------
print_info "Setting up Dashboard (Next.js)..."

cd "$AETHER_DIR"
npm install

print_status "Dashboard ready"

# ---------------- Start Services ----------------
print_info "Starting all services..."

# Start AI Core
cd "$AETHER_DIR/apps/ai-core"
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > ai-core.log 2>&1 &
AI_CORE_PID=$!

sleep 5

# Start Rust Agent
cd "$AETHER_DIR/apps/agent"
nohup cargo run --release > agent.log 2>&1 &
AGENT_PID=$!

sleep 3

# Start Go Orchestrator
cd "$AETHER_DIR/apps/orchestrator"
nohup ./orchestrator > orchestrator.log 2>&1 &
ORCHESTRATOR_PID=$!

sleep 3

# Start Dashboard
cd "$AETHER_DIR"
nohup npm run dev > dashboard.log 2>&1 &
DASHBOARD_PID=$!

sleep 5

print_status "All services started"

# ---------------- Verification ----------------
print_info "Verifying services..."
services_ok=true

if ! curl -s http://localhost:8000/docs > /dev/null; then
    print_warning "AI Core API not responding"
    services_ok=false
else
    print_status "AI Core API: http://localhost:8000"
fi

if ! curl -s http://localhost:8080/submit > /dev/null 2>&1; then
    print_warning "Orchestrator API not responding"
    services_ok=false
else
    print_status "Orchestrator API: http://localhost:8080"
fi

if ! curl -s http://localhost:3000 > /dev/null; then
    print_warning "Dashboard not responding"
    services_ok=false
else
    print_status "Dashboard: http://localhost:3000"
fi

# ---------------- Save PIDs ----------------
print_info "Saving process information..."

cat > "$PROJECT_ROOT/aether.pids" << EOF
# Aether Process IDs - Generated $(date)
AI_CORE_PID=$AI_CORE_PID
AGENT_PID=$AGENT_PID
ORCHESTRATOR_PID=$ORCHESTRATOR_PID
DASHBOARD_PID=$DASHBOARD_PID
EOF

echo -e "${GREEN}🎉 Aether Setup Complete!${NC}"
echo "Logs:"
echo "  AI Core: aether/apps/ai-core/ai-core.log"
echo "  Agent:   aether/apps/agent/agent.log"
echo "  Orchestrator: aether/apps/orchestrator/orchestrator.log"
echo "  Dashboard: aether/dashboard.log"
