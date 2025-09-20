#!/bin/bash

# Aether GPU Telemetry and Scheduling System - Linux Setup Script
# This script sets up the entire Aether project infrastructure and services on Linux

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

echo -e "${BLUE}🚀 Aether GPU Telemetry and Scheduling System Setup (Linux)${NC}"
echo -e "${BLUE}==========================================================${NC}"
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

# Detect Linux distribution
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO=$ID
        VERSION=$VERSION_ID
    else
        print_error "Cannot detect Linux distribution. /etc/os-release not found."
        exit 1
    fi
}

# Package manager functions
install_package() {
    local package=$1
    print_info "Installing $package..."
    
    case $DISTRO in
        ubuntu|debian)
            sudo apt-get update -qq
            sudo apt-get install -y $package
            ;;
        fedora)
            sudo dnf install -y $package
            ;;
        centos|rhel)
            sudo yum install -y $package
            ;;
        arch|manjaro)
            sudo pacman -S --noconfirm $package
            ;;
        opensuse*)
            sudo zypper install -y $package
            ;;
        *)
            print_error "Unsupported Linux distribution: $DISTRO"
            print_info "Supported distributions: Ubuntu, Debian, Fedora, CentOS, RHEL, Arch, Manjaro, openSUSE"
            exit 1
            ;;
    esac
}

# Helper functions for Docker installation
install_docker_official_ubuntu_debian() {
    # Remove old versions
    sudo apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true
    
    # Install prerequisites
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl gnupg lsb-release || return 1
    
    # Add Docker's official GPG key
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL "https://download.docker.com/linux/$DISTRO/gpg" | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg || return 1
    
    # Add Docker repository
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$DISTRO $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null || return 1
    
    # Install Docker Engine
    sudo apt-get update || return 1
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin || return 1
    return 0
}

install_docker_official_fedora() {
    sudo dnf remove -y docker docker-client docker-client-latest docker-common docker-latest docker-latest-logrotate docker-logrotate docker-selinux docker-engine-selinux docker-engine 2>/dev/null || true
    sudo dnf install -y dnf-plugins-core || return 1
    sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo || return 1
    sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin || return 1
    return 0
}

install_docker_official_centos_rhel() {
    sudo yum remove -y docker docker-client docker-client-latest docker-common docker-latest docker-latest-logrotate docker-logrotate docker-engine 2>/dev/null || true
    sudo yum install -y yum-utils || return 1
    sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo || return 1
    sudo yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin || return 1
    return 0
}

install_docker_alternative() {
    print_info "Trying alternative Docker installation using convenience script..."
    curl -fsSL https://get.docker.com -o get-docker.sh || {
        print_error "Failed to download Docker convenience script"
        return 1
    }
    
    sudo sh get-docker.sh || {
        print_error "Docker convenience script installation failed"
        rm -f get-docker.sh
        return 1
    }
    
    rm -f get-docker.sh
    print_info "Alternative Docker installation completed"
    return 0
}

# Install Docker
install_docker() {
    # Check if Docker service exists first
    local docker_service_exists=false
    if systemctl list-unit-files | grep -q "docker.service"; then
        docker_service_exists=true
    fi
    
    if command -v docker &> /dev/null && [ "$docker_service_exists" = true ]; then
        print_info "Docker is already installed"
        
        # Ensure Docker service is running
        if ! systemctl is-active --quiet docker; then
            print_info "Starting Docker service..."
            sudo systemctl start docker
            sudo systemctl enable docker
        fi
        
        # Check if user is in docker group
        local actual_user="${SUDO_USER:-$USER}"
        if ! groups "$actual_user" | grep -q docker; then
            print_info "Adding $actual_user to docker group..."
            sudo usermod -aG docker "$actual_user"
            print_warning "You may need to log out and back in for Docker group membership to take effect"
            print_info "Alternatively, you can run: newgrp docker"
        fi
        
        return 0
    fi
    
    print_info "Installing Docker..."
    
    # First try to install using distribution package manager
    case $DISTRO in
            ubuntu|debian)
                # Try official Docker repository method first
                if ! install_docker_official_ubuntu_debian; then
                    print_warning "Official Docker installation failed, trying alternative method..."
                    install_docker_alternative
                fi
                ;;
            fedora)
                # Try official Docker repository method first
                if ! install_docker_official_fedora; then
                    print_warning "Official Docker installation failed, trying alternative method..."
                    install_docker_alternative
                fi
                ;;
            centos|rhel)
                # Try official Docker repository method first
                if ! install_docker_official_centos_rhel; then
                    print_warning "Official Docker installation failed, trying alternative method..."
                    install_docker_alternative
                fi
                ;;
            arch|manjaro)
                sudo pacman -S --noconfirm docker docker-compose
                ;;
            opensuse*)
                sudo zypper install -y docker docker-compose
                ;;
    esac
        
        # Wait for Docker to be properly installed
        sleep 3
        
        # Verify Docker installation
        if ! command -v docker &> /dev/null; then
            print_error "Docker installation failed - docker command not found"
            exit 1
        fi
        
        # Check if Docker service is now available
        if ! systemctl list-unit-files | grep -q "docker.service"; then
            print_error "Docker service unit file not found after installation"
            print_info "Attempting to reload systemd daemon..."
            sudo systemctl daemon-reload
            sleep 2
            
            if ! systemctl list-unit-files | grep -q "docker.service"; then
                print_error "Docker service still not available after daemon reload"
                print_info "You may need to restart your system or manually install Docker"
                exit 1
            fi
        fi
        
        # Start and enable Docker service
        print_info "Starting and enabling Docker service..."
        sudo systemctl start docker || {
            print_error "Failed to start Docker service"
            print_info "Checking Docker service status..."
            sudo systemctl status docker --no-pager || true
            exit 1
        }
        
        sudo systemctl enable docker || {
            print_warning "Failed to enable Docker service for auto-start"
        }
        
        # Verify Docker is running
        local attempts=0
        while [ $attempts -lt 10 ]; do
            if docker info &> /dev/null; then
                break
            fi
            print_info "Waiting for Docker daemon to start... (attempt $((attempts + 1))/10)"
            sleep 2
            ((attempts++))
        done
        
        if ! docker info &> /dev/null; then
            print_error "Docker daemon failed to start properly"
            sudo systemctl status docker --no-pager || true
            exit 1
        fi
        
        # Add current user to docker group
        local actual_user="${SUDO_USER:-$USER}"
        sudo usermod -aG docker "$actual_user"
        print_warning "You may need to log out and back in for Docker group membership to take effect"
        print_info "Alternatively, you can run: newgrp docker"
        
        print_status "Docker installed and started successfully"
}

# Install Node.js
install_nodejs() {
    if command -v node &> /dev/null; then
        print_info "Node.js is already installed ($(node --version))"
        return 0
    fi
    
    print_info "Installing Node.js..."
    
    case $DISTRO in
        ubuntu|debian)
            curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
            sudo apt-get install -y nodejs
            ;;
        fedora)
            sudo dnf install -y nodejs npm
            ;;
        centos|rhel)
            curl -fsSL https://rpm.nodesource.com/setup_lts.x | sudo bash -
            sudo yum install -y nodejs
            ;;
        arch|manjaro)
            sudo pacman -S --noconfirm nodejs npm
            ;;
        opensuse*)
            sudo zypper install -y nodejs20 npm20
            ;;
    esac
}

# Install Go
install_go() {
    if command -v go &> /dev/null; then
        print_info "Go is already installed ($(go version))"
        return 0
    fi
    
    print_info "Installing Go..."
    
    # Download and install Go
    GO_VERSION="1.21.3"
    GO_ARCH="linux-amd64"
    
    # Detect architecture
    ARCH=$(uname -m)
    case $ARCH in
        x86_64)
            GO_ARCH="linux-amd64"
            ;;
        aarch64|arm64)
            GO_ARCH="linux-arm64"
            ;;
        armv6l)
            GO_ARCH="linux-armv6l"
            ;;
        *)
            print_error "Unsupported architecture: $ARCH"
            exit 1
            ;;
    esac
    
    cd /tmp
    wget -q "https://go.dev/dl/go${GO_VERSION}.${GO_ARCH}.tar.gz"
    
    # Remove existing installation if it exists
    if [ -d "/usr/local/go" ]; then
        print_info "Removing existing Go installation..."
        sudo rm -rf /usr/local/go
    fi
    
    sudo tar -C /usr/local -xzf "go${GO_VERSION}.${GO_ARCH}.tar.gz"
    
    # Add Go to PATH in common shell profiles
    if ! grep -q "/usr/local/go/bin" /etc/profile; then
        echo 'export PATH=$PATH:/usr/local/go/bin' | sudo tee -a /etc/profile
    fi
    
    local actual_user="${SUDO_USER:-$USER}"
    local actual_home="${SUDO_USER:+$(getent passwd "$SUDO_USER" | cut -d: -f6)}"
    actual_home="${actual_home:-$HOME}"
    
    # Add to user's profile files if not already present
    if [ -f "$actual_home/.bashrc" ] && ! grep -q "/usr/local/go/bin" "$actual_home/.bashrc"; then
        echo 'export PATH=$PATH:/usr/local/go/bin' >> "$actual_home/.bashrc"
    fi
    if [ -f "$actual_home/.profile" ] && ! grep -q "/usr/local/go/bin" "$actual_home/.profile"; then
        echo 'export PATH=$PATH:/usr/local/go/bin' >> "$actual_home/.profile"
    fi
    
    # Source the profile for current session
    export PATH=$PATH:/usr/local/go/bin
    
    rm "/tmp/go${GO_VERSION}.${GO_ARCH}.tar.gz"
}

# Install Rust
install_rust() {
    local actual_user="${SUDO_USER:-$USER}"
    local actual_home="${SUDO_USER:+$(getent passwd "$SUDO_USER" | cut -d: -f6)}"
    actual_home="${actual_home:-$HOME}"
    
    # Check if cargo is available or exists in user's cargo directory
    if command -v cargo &> /dev/null; then
        print_info "Rust is already available in PATH"
        return 0
    elif [ -f "$actual_home/.cargo/bin/cargo" ]; then
        print_info "Rust already installed in $actual_home/.cargo"
        # Add to PATH for current session
        export PATH="$actual_home/.cargo/bin:$PATH"
        source "$actual_home/.cargo/env" 2>/dev/null || true
        return 0
    else
        print_info "Installing Rust..."
        
        if [ "$EUID" -eq 0 ] && [ -n "$SUDO_USER" ]; then
            # Running as root via sudo, install for the actual user
            sudo -u "$SUDO_USER" bash -c 'curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y'
            # Source the cargo environment for the current session
            source "$actual_home/.cargo/env"
        else
            # Normal installation
            curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
            source ~/.cargo/env
        fi
    fi
}

# Install Miniconda
install_miniconda() {
    # Check if conda is available for the actual user (not root when using sudo)
    local actual_user="${SUDO_USER:-$USER}"
    local actual_home="${SUDO_USER:+$(getent passwd "$SUDO_USER" | cut -d: -f6)}"
    actual_home="${actual_home:-$HOME}"
    
    # Check if conda exists in user's home directory or is in PATH
    if command -v conda &> /dev/null; then
        print_info "Conda is already available in PATH"
        return 0
    elif [ -f "$actual_home/miniconda3/bin/conda" ]; then
        print_info "Miniconda already installed in $actual_home/miniconda3"
        # Add to PATH for current session
        export PATH="$actual_home/miniconda3/bin:$PATH"
        return 0
    elif [ -f "$actual_home/anaconda3/bin/conda" ]; then
        print_info "Anaconda already installed in $actual_home/anaconda3"
        # Add to PATH for current session
        export PATH="$actual_home/anaconda3/bin:$PATH"
        return 0
    else
        print_info "Installing Miniconda..."
        
        # Detect architecture
        ARCH=$(uname -m)
        case $ARCH in
            x86_64)
                CONDA_ARCH="x86_64"
                ;;
            aarch64|arm64)
                CONDA_ARCH="aarch64"
                ;;
            *)
                print_error "Unsupported architecture for Miniconda: $ARCH"
                exit 1
                ;;
        esac
        
        cd /tmp
        wget -q "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-${CONDA_ARCH}.sh"
        
        # Install for the actual user, not root
        if [ "$EUID" -eq 0 ] && [ -n "$SUDO_USER" ]; then
            # Running as root via sudo, install for the actual user
            sudo -u "$SUDO_USER" bash "Miniconda3-latest-Linux-${CONDA_ARCH}.sh" -b -p "$actual_home/miniconda3"
            
            # Add conda to PATH in user's shell files
            sudo -u "$SUDO_USER" bash -c "echo 'export PATH=\"\$HOME/miniconda3/bin:\$PATH\"' >> $actual_home/.bashrc"
            sudo -u "$SUDO_USER" bash -c "echo 'export PATH=\"\$HOME/miniconda3/bin:\$PATH\"' >> $actual_home/.profile"
            
            # Initialize conda for the user
            sudo -u "$SUDO_USER" "$actual_home/miniconda3/bin/conda" init bash
        else
            # Normal installation
            bash "Miniconda3-latest-Linux-${CONDA_ARCH}.sh" -b -p "$actual_home/miniconda3"
            
            # Add conda to PATH
            echo 'export PATH="$HOME/miniconda3/bin:$PATH"' >> ~/.bashrc
            echo 'export PATH="$HOME/miniconda3/bin:$PATH"' >> ~/.profile
            
            # Initialize conda
            "$actual_home/miniconda3/bin/conda" init bash
        fi
        
        # Add to PATH for current session
        export PATH="$actual_home/miniconda3/bin:$PATH"
        
        rm "/tmp/Miniconda3-latest-Linux-${CONDA_ARCH}.sh"
        
        print_warning "Please restart your shell or run 'source ~/.bashrc' to use conda"
    fi
}

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    print_error "This setup script is designed for Linux. For macOS, use setup.sh instead."
    exit 1
fi

# Check if running with sudo - warn but continue
if [ "$EUID" -eq 0 ] && [ -n "$SUDO_USER" ]; then
    print_warning "Running with sudo detected. This is OK for system package installation."
    print_info "User: $SUDO_USER, Home: $(getent passwd "$SUDO_USER" | cut -d: -f6)"
elif [ "$EUID" -eq 0 ]; then
    print_error "Please don't run this script as root directly. Use sudo if needed."
    print_info "Recommended usage: ./setup_linux.sh (you'll be prompted for sudo when needed)"
    exit 1
fi

# Detect Linux distribution
print_info "Detecting Linux distribution..."
detect_distro
print_info "Detected: $DISTRO $VERSION"

# Check for sudo access
if ! sudo -n true 2>/dev/null; then
    print_info "This script requires sudo access for installing system packages."
    print_info "You may be prompted for your password."
fi

# Check for required tools and install if missing
print_info "Checking and installing system requirements..."

# Install curl and wget if not present
if ! command -v curl &> /dev/null || ! command -v wget &> /dev/null; then
    case $DISTRO in
        ubuntu|debian)
            install_package "curl wget"
            ;;
        fedora)
            install_package "curl wget"
            ;;
        centos|rhel)
            install_package "curl wget"
            ;;
        arch|manjaro)
            install_package "curl wget"
            ;;
        opensuse*)
            install_package "curl wget"
            ;;
    esac
fi

# Install Docker
install_docker

# Check if Docker is running, start if not
print_info "Verifying Docker installation and service..."
if ! command -v docker &> /dev/null; then
    print_error "Docker command not found after installation"
    exit 1
fi

if ! systemctl list-unit-files | grep -q "docker.service"; then
    print_error "Docker service not found. Installation may have failed."
    exit 1
fi

if ! docker info &> /dev/null; then
    print_info "Starting Docker service..."
    sudo systemctl start docker || {
        print_error "Failed to start Docker service"
        sudo systemctl status docker --no-pager || true
        exit 1
    }
    
    # Wait for Docker to start
    local attempts=0
    while [ $attempts -lt 10 ]; do
        if docker info &> /dev/null; then
            break
        fi
        print_info "Waiting for Docker daemon... (attempt $((attempts + 1))/10)"
        sleep 2
        ((attempts++))
    done
    
    if ! docker info &> /dev/null; then
        print_error "Docker daemon failed to start. Please check Docker installation and try again."
        sudo systemctl status docker --no-pager || true
        exit 1
    fi
fi

print_status "Docker is running and ready"

# Install Rust
install_rust

# Install Go
install_go

# Install Node.js
install_nodejs

# Install Miniconda
install_miniconda

print_status "All system requirements installed"

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

# Make sure conda is available in this script
if command -v conda &> /dev/null; then
    # Initialize conda for this shell session
    eval "$(conda shell.bash hook)"
    
    # Check if conda environment exists using conda info --envs
    if conda info --envs | grep -q "aether-ai"; then
        print_info "Conda environment 'aether-ai' already exists"
    else
        print_info "Creating conda environment 'aether-ai'..."
        conda create -n aether-ai python=3.9 -y
    fi

    # Activate environment and install dependencies
    print_info "Installing Python dependencies..."
    conda activate aether-ai
    
    # Set environment variables to prevent threading issues during training
    export OMP_NUM_THREADS=1
    export OPENBLAS_NUM_THREADS=1
    export MKL_NUM_THREADS=1
    export VECLIB_MAXIMUM_THREADS=1
    export NUMEXPR_NUM_THREADS=1
    
    pip install -r requirements.txt

    # Generate training data and train model
    print_info "Generating training data..."
    python simulator.py

    print_info "Training AI model..."
    if python train.py; then
        print_status "AI model training completed successfully"
    else
        print_warning "AI model training failed. This may be due to system library conflicts."
        print_info "The system will continue with a fallback model if available."
        
        # Check if any model file was created as fallback
        if [ ! -f "scheduler_model.pkl" ]; then
            print_warning "No model file found. Creating a minimal fallback model..."
            cat > create_fallback_model.py << 'EOF'
import joblib
from sklearn.dummy import DummyClassifier
import numpy as np

# Create a simple fallback model
model = DummyClassifier(strategy="most_frequent")
X_dummy = np.array([[50, 5000, 0, 50, 150, 0]] * 100)
y_dummy = np.array([1] * 60 + [0] * 40)
model.fit(X_dummy, y_dummy)
joblib.dump(model, 'scheduler_model.pkl')
print("Fallback model created")
EOF
            python create_fallback_model.py
            rm create_fallback_model.py
        fi
    fi
else
    print_error "Conda not found. Please restart your shell and run the script again."
    exit 1
fi

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
if command -v conda &> /dev/null; then
    eval "$(conda shell.bash hook)"
    conda activate aether-ai
    nohup uvicorn main:app --host 0.0.0.0 --port 8000 > ai-core.log 2>&1 &
    AI_CORE_PID=$!
else
    print_error "Conda not available. Cannot start AI Core."
    exit 1
fi

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
echo -e "${GREEN}🎉 Aether Linux Setup Complete!${NC}"
echo -e "${GREEN}===============================${NC}"
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
echo "  • AI Core:         apps/ai-core/ai-core.log"
echo "  • Agent:           apps/agent/agent.log"
echo "  • Orchestrator:    apps/orchestrator/orchestrator.log"
echo "  • Dashboard:       dashboard.log"
echo ""
echo -e "${YELLOW}To stop all services:${NC} ./stop.sh"
echo -e "${YELLOW}To view logs:${NC} tail -f apps/*/ai-core.log"
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
echo ""
echo -e "${YELLOW}Important Notes:${NC}"
echo "• If you installed Docker for the first time, you may need to:"
echo "  - Log out and back in, or run: newgrp docker"
echo "• If conda was just installed, restart your shell or run: source ~/.bashrc"
echo "• Supported Linux distributions: Ubuntu, Debian, Fedora, CentOS, RHEL, Arch, Manjaro, openSUSE"