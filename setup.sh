#!/bin/bash

# Aether GPU Telemetry and Scheduling System - Complete Setup Script
# This script sets up the entire Aether project infrastructure and services

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AETHER_DIR="$PROJECT_ROOT/nebula-aether"

echo -e "${BLUE}🚀 Aether GPU Telemetry and Scheduling System Setup${NC}"
echo -e "${BLUE}================================================${NC}"
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

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    print_error "This setup script is designed for macOS. Please adapt for your OS."
    exit 1
fi

# Check for required tools
print_info "Checking system requirements..."

# Check Docker
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker Desktop from https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    print_error "Docker is not running. Please start Docker Desktop and try again."
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
    print_error "Go is not installed. Please install Go from https://golang.org/dl/"
    exit 1
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    print_error "Node.js is not installed. Please install Node.js from https://nodejs.org/"
    exit 1
fi

# Check Conda
if ! command -v conda &> /dev/null; then
    print_error "Conda is not installed. Please install Miniconda from https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

print_status "All system requirements met"

# Step 1: Start Infrastructure
print_info "Starting infrastructure services (NATS, TimescaleDB)..."

cd "$AETHER_DIR"

# Stop any existing containers
docker compose down 2>/dev/null || true

# Start infrastructure
docker compose up -d

# Wait for services to be ready
print_info "Waiting for services to start..."
sleep 10

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

# Step 2: Setup Database Schema
print_info "Setting up database schema..."

# Wait a bit more for TimescaleDB to be fully ready
sleep 5

# Create the database and table if they don't exist
docker compose exec -T timescaledb psql -U aether -d postgres -c "CREATE DATABASE aether;" 2>/dev/null || true

# Create the gpu_telemetry table with all columns
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

# Convert to hypertable
docker compose exec -T timescaledb psql -U aether -d aether -c "SELECT create_hypertable('gpu_telemetry', 'time', if_not_exists => TRUE);" 2>/dev/null || true

print_status "Database schema ready"

# Step 3: Setup Python AI Core
print_info "Setting up AI Core (Python)..."

cd "$AETHER_DIR/apps/ai-core"

# Create conda environment if it doesn't exist
if ! conda env list | grep -q "aether-ai"; then
    print_info "Creating conda environment 'aether-ai'..."
    conda create -n aether-ai python=3.9 -y
fi

# Activate environment and install dependencies
print_info "Installing Python dependencies..."
eval "$(conda shell.bash hook)"
conda activate aether-ai
pip install -r requirements.txt

# Generate training data and train model
print_info "Generating training data..."
python simulator.py

print_info "Training AI model..."
python train.py

print_status "AI Core ready"

# Step 4: Setup Rust Agent
print_info "Setting up Rust Agent..."

cd "$AETHER_DIR/apps/agent"

# Install Rust dependencies
cargo build --release

print_status "Rust Agent ready"

# Step 5: Setup Go Orchestrator
print_info "Setting up Go Orchestrator..."

cd "$AETHER_DIR/apps/orchestrator"

# Download Go dependencies
go mod tidy

# Build orchestrator
go build -o orchestrator main.go

print_status "Go Orchestrator ready"

# Step 6: Setup Dashboard
print_info "Setting up Dashboard (Next.js)..."

cd "$AETHER_DIR"

# Install Node.js dependencies
npm install

print_status "Dashboard ready"

# Step 7: Start All Services
print_info "Starting all services..."

# Start AI Core in background
print_info "Starting AI Core API..."
cd "$AETHER_DIR/apps/ai-core"
conda activate aether-ai
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > ai-core.log 2>&1 &
AI_CORE_PID=$!

# Wait for AI Core to start
sleep 5

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

# Step 8: Verification
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

# Step 9: Test Job Submission
print_info "Testing job submission..."

# Submit a test job
response=$(curl -s -X POST http://localhost:8080/submit \
    -H "Content-Type: application/json" \
    -d '{"id": "setup-test-job", "type": "training"}')

if echo "$response" | grep -q "job added"; then
    print_status "Job submission test successful"
else
    print_warning "Job submission test failed: $response"
fi

# Step 10: Save Process IDs
print_info "Saving process information..."

cat > "$PROJECT_ROOT/aether.pids" << EOF
# Aether Process IDs - Generated $(date)
AI_CORE_PID=$AI_CORE_PID
AGENT_PID=$AGENT_PID
ORCHESTRATOR_PID=$ORCHESTRATOR_PID
DASHBOARD_PID=$DASHBOARD_PID
EOF

# Step 11: Final Status
echo ""
echo -e "${GREEN}🎉 Aether Setup Complete!${NC}"
echo -e "${GREEN}========================${NC}"
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
echo -e "${YELLOW}To view logs:${NC} tail -f aether/apps/*/ai-core.log"
echo ""

if [ "$services_ok" = true ]; then
    print_status "All services are running correctly!"
    echo -e "${GREEN}🚀 Ready to use Aether GPU Telemetry and Scheduling System!${NC}"
else
    print_warning "Some services may not be running correctly. Check the logs above."
fi

echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "1. Open http://localhost:3000 in your browser to view the dashboard"
echo "2. Submit jobs via: curl -X POST http://localhost:8080/submit -H 'Content-Type: application/json' -d '{\"id\": \"my-job\", \"type\": \"training\"}'"
echo "3. Monitor GPU telemetry in real-time on the dashboard"
echo "4. Check AI Core API documentation at http://localhost:8000/docs"
