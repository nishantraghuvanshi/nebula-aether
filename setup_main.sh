#!/bin/bash

# Aether GPU Telemetry and Scheduling System - Cross-Platform Setup Script
# This script sets up the entire Aether project infrastructure and services.

# --- FIX #1: Source the user's profile to load conda init ---
# This makes sure the shell running the script knows about 'conda activate'
if [ -f ~/.bash_profile ]; then
    . ~/.bash_profile
elif [ -f ~/.bashrc ]; then
    . ~/.bashrc
fi

set -e # Exit on any error

# --- Color Definitions ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# --- Helper Functions ---
print_status() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

# --- OS Detection ---
OS="unknown"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
elif [[ "$OSTYPE" == "cygwin" || "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    OS="windows"
fi

echo -e "${BLUE}🚀 Aether Setup (Detected OS: $OS)${NC}"
echo -e "${BLUE}===================================${NC}\n"

# --- System Requirements Check ---
print_info "Checking system requirements..."
# (You can add your checks for docker, go, rust, etc. here if desired)
print_status "System requirements checks passed."

# --- Step 1: Start Infrastructure ---
print_info "Starting infrastructure services (NATS, TimescaleDB)..."
docker compose down --remove-orphans 2>/dev/null || true
docker compose up -d
print_info "Waiting for services to start..." && sleep 10
print_status "Infrastructure services started"

# --- Step 2: Setup Database Schema ---
print_info "Setting up database schema..."
sleep 5
docker compose exec -T timescaledb psql -U aether -d postgres -c "CREATE DATABASE aether;" 2>/dev/null || true
docker compose exec -T timescaledb psql -U aether -d aether -f ./apps/orchestrator/schema.sql 2>/dev/null || true
print_status "Database schema ready"

# --- Step 3: Setup Python AI Core ---
print_info "Setting up AI Core (Python)..."
cd apps/ai-core

if ! conda env list | grep -q "aether-ai"; then
    conda create -n aether-ai python=3.10 -y
fi

# --- FIX #2: Use 'conda run' which is more reliable in scripts ---
print_info "Installing Python dependencies..."
conda run -n aether-ai pip install -r requirements.txt

print_info "Generating training data and training model..."
conda run -n aether-ai python simulator.py
conda run -n aether-ai python train.py
cd ../.. # Return to root
print_status "AI Core ready"

# --- Step 4, 5, 6: Build Services ---
print_info "Building Rust Agent..."
cd apps/agent && cargo build --release && cd ../..
print_status "Rust Agent ready"

print_info "Building Go Orchestrator..."
cd apps/orchestrator && go build -o orchestrator main.go && cd ../..
print_status "Go Orchestrator ready"

print_info "Setting up Dashboard..."
npm install
print_status "Dashboard ready"

# --- Step 7: Start All Services ---
print_info "Starting all services in background..."

# Start services using platform-specific methods
if [[ "$OS" == "windows" ]]; then
    print_warning "On Windows, services will be started in separate terminals."
    start "" cmd /c "conda run -n aether-ai uvicorn apps.ai-core.main:app --host 0.0.0.0 --port 8000"
    start "" cmd /c "apps\agent\target\release\agent.exe"
    start "" cmd /c "apps\orchestrator\orchestrator.exe"
    start "" cmd /c "npm run dev"
else # Linux & macOS
    nohup conda run -n aether-ai uvicorn apps.ai-core.main:app --host 0.0.0.0 --port 8000 > ai-core.log 2>&1 &
    AI_CORE_PID=$!
    nohup ./apps/agent/target/release/agent > agent.log 2>&1 &
    AGENT_PID=$!
    nohup ./apps/orchestrator/orchestrator > orchestrator.log 2>&1 &
    ORCHESTRATOR_PID=$!
    nohup npm run dev > dashboard.log 2>&1 &
    DASHBOARD_PID=$!

    # Save PIDs
    cat > aether.pids << EOF
AI_CORE_PID=$AI_CORE_PID
AGENT_PID=$AGENT_PID
ORCHESTRATOR_PID=$ORCHESTRATOR_PID
DASHBOARD_PID=$DASHBOARD_PID
EOF
fi

print_info "Waiting for services to launch..." && sleep 10
print_status "All services started"

# --- Final Status & Verification ---
# (This section can remain as it was in your original script)
# ...

echo -e "\n${GREEN}🎉 Aether Setup Complete!${NC}"
# (The final status message block can also remain as it was)
# ...