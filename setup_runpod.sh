#!/bin/bash

# RunPod Setup Script for Aether GPU Telemetry Agent
# Version: 1.0 - Complete HTTP Polling Implementation
#
# IMPORTANT: Save this file in /workspace/setup_runpod.sh on your RunPod instance
# Run: chmod +x /workspace/setup_runpod.sh && /workspace/setup_runpod.sh
#
# This script handles RunPod's restart behavior where everything outside /workspace is lost

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 RunPod Aether Agent Setup Script${NC}"
echo -e "${BLUE}====================================${NC}"
echo ""
echo -e "${YELLOW}⚠️  RUNPOD PERSISTENCE INFO:${NC}"
echo "   • Only /workspace is persistent across pod restarts"
echo "   • All system packages, Rust, etc. are lost on restart"
echo "   • This script reinstalls everything needed"
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

# Step 1: System Package Updates
print_info "Updating system packages..."
apt update -qq

# Step 2: Install Essential Dependencies
print_info "Installing essential dependencies..."
apt install -y pkg-config libssl-dev git curl build-essential

# Step 3: Install Rust (always needed on RunPod restart)
if ! command -v cargo &> /dev/null; then
    print_info "Installing Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source ~/.cargo/env
else
    print_info "Rust found, sourcing environment..."
    source ~/.cargo/env
fi

print_status "Rust installation complete"

# Step 4: Create NVIDIA ML symlink (required for GPU access)
print_info "Setting up NVIDIA GPU access..."
if [ -f "/usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1" ]; then
    ln -sf /usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1 /usr/lib/x86_64-linux-gnu/libnvidia-ml.so
    print_status "NVIDIA ML library symlink created"
else
    print_warning "NVIDIA libraries not found - GPU detection may fail"
fi

# Step 5: Navigate to workspace and setup repository
print_info "Setting up Aether repository..."
cd /workspace

# Clone or update repository
if [ ! -d "nebula-aether" ]; then
    print_info "Cloning nebula-aether repository..."
    git clone https://github.com/nishantraghuvanshi/nebula-aether.git
    cd nebula-aether
    git checkout moksh
else
    print_info "Updating existing repository..."
    cd nebula-aether
    git fetch origin
    git checkout moksh
    git pull origin moksh
fi

print_status "Repository setup complete"

# Step 6: Build the Rust agent
print_info "Building Rust agent..."
cd apps/agent

# Ensure Rust environment is available
source ~/.cargo/env

# Build the agent
cargo build --release

print_status "Rust agent built successfully"

# Step 7: Configuration Summary
echo ""
echo -e "${GREEN}🎉 RunPod Setup Complete!${NC}"
echo -e "${GREEN}========================${NC}"
echo ""
echo -e "${BLUE}📋 Configuration Summary:${NC}"
echo "  • Repository: /workspace/nebula-aether"
echo "  • Branch: moksh (with HTTP polling implementation)"
echo "  • Agent binary: /workspace/nebula-aether/apps/agent/target/release/agent"
echo "  • Dependencies: Rust, OpenSSL, NVIDIA drivers configured"
echo ""
echo -e "${BLUE}🔗 Connection Details:${NC}"
echo "  • NATS Server: nats://0.tcp.in.ngrok.io:10544"
echo "  • HTTP Polling: https://b172e93381d8.ngrok-free.app"
echo "  • Orchestrator API: https://b172e93381d8.ngrok-free.app"
echo ""

# Step 8: Test GPU Detection
print_info "Testing GPU detection..."
if command -v nvidia-smi &> /dev/null; then
    echo -e "${GREEN}🎯 NVIDIA GPU detected:${NC}"
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits | head -1
    print_status "Real GPU telemetry will be used"
else
    print_warning "nvidia-smi not found - agent will run in mock mode"
fi

echo ""
echo -e "${BLUE}🚀 Ready to Run!${NC}"
echo ""
echo -e "${YELLOW}To start the agent:${NC}"
echo "  cd /workspace/nebula-aether/apps/agent"
echo "  source ~/.cargo/env"
echo "  cargo run --release"
echo ""
echo -e "${YELLOW}Expected behavior:${NC}"
echo "  ✅ Connect to NATS at nats://0.tcp.in.ngrok.io:10544"
echo "  ✅ Detect GPU: NVIDIA RTX 2000 Ada Generation (real GPU only)"
echo "  ✅ Send telemetry every 5 seconds"
echo "  ✅ Poll for jobs every 5 seconds via HTTPS"
echo "  ✅ Execute jobs received from orchestrator"
echo "  ❌ No mock GPUs will appear in dashboard"
echo ""
echo -e "${BLUE}💡 Pro Tips:${NC}"
echo "  • Save this script in /workspace for future pod restarts"
echo "  • Use 'screen' or 'tmux' to run agent in background"
echo "  • Monitor logs for job execution messages"
echo "  • Submit jobs via dashboard at http://localhost:3000"
echo ""

# Step 9: Quick Test Run (optional)
read -p "$(echo -e ${YELLOW}Would you like to run a quick test? [y/N]: ${NC})" -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Running quick test..."
    cd /workspace/nebula-aether/apps/agent
    source ~/.cargo/env
    timeout 10s cargo run --release || print_info "Test completed (timeout after 10s)"
fi

echo ""
print_status "Setup script completed successfully!"
echo -e "${GREEN}Ready for GPU job execution! 🎯${NC}"