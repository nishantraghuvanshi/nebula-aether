# Nebula Aether Operations Guide

## System Architecture Overview

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   Local Mac     │    │    ngrok     │    │    RunPod GPU   │
├─────────────────┤    │   Tunnels    │    │    Instances    │
│ Dashboard:3000  │    │              │    │                 │
│ Orchestrator:8080│◄──►│ HTTP tunnel  │◄──►│ Rust Agent      │
│ NATS:4222       │    │ TCP tunnel   │    │ Job Execution   │
│ TimescaleDB:5432│    │              │    │ GPU Monitoring  │
└─────────────────┘    └──────────────┘    └─────────────────┘
```

## Component Responsibilities

**Local Services (Mac):**
- **Dashboard**: Web UI for job submission and monitoring
- **Orchestrator**: Job queue management, GPU coordination
- **NATS**: Message bus for real-time communication
- **TimescaleDB**: Time-series storage for GPU telemetry
- **ngrok**: Exposes local services to remote GPU instances

**Remote Services (RunPod):**
- **Agent**: GPU monitoring, job execution, health reporting

## 🚀 Starting the System

### Method 1: Complete System Startup (Recommended)
```bash
cd /Users/moksh/Desktop/c/nebula/nebula-aether

# Start everything with one command
./startup.sh
```

**What `startup.sh` does:**
- Kills existing processes (clean slate)
- Starts Docker containers (NATS, TimescaleDB)
- Starts ngrok tunnels (both TCP and HTTP)
- Automatically updates URLs in all files
- Starts orchestrator and dashboard
- Displays service status and URLs

### Method 2: Services Only (if infrastructure running)
```bash
# If Docker and ngrok are already running
./start_services.sh
```

### Method 3: URL Update Only (if ngrok restarted)
```bash
# If only ngrok URLs changed
./update_ngrok_urls.sh
git push  # Sync to RunPod
```

### Verify Services
```bash
# Check service status
echo "=== Service Status ==="
curl -s http://localhost:3000 > /dev/null && echo "✅ Dashboard: http://localhost:3000" || echo "❌ Dashboard failed"
curl -s "http://localhost:8080/poll?gpu_id=test" > /dev/null && echo "✅ Orchestrator API" || echo "❌ Orchestrator failed"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "(nats|timescaledb)"
```

## 🛑 Stopping the System

### Complete System Stop (Recommended)
```bash
# Stop everything with one command
./stop_system.sh
```

**What `stop_system.sh` does:**
- Stops application processes (orchestrator, dashboard)
- Stops ngrok tunnels
- Force-kills processes by port (backup cleanup)
- Stops Docker containers
- Cleans up PID files

### Manual Stop (if script fails)
```bash
# Kill application processes
pkill -f "go run.*orchestrator"
pkill -f "npm run dev"
pkill ngrok

# Force kill by port
lsof -ti:8080 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true

# Stop Docker services
docker compose down
```

## 🔄 Restart Workflow

### Complete Restart (after system reboot)
```bash
cd /Users/moksh/Desktop/c/nebula/nebula-aether

# Complete restart with one command
./startup.sh

# Sync new URLs to RunPod
git add -A && git commit -m "Update ngrok URLs: $(date)" && git push
```

### Quick Restart (services only)
```bash
# Restart just the application services
./start_services.sh
```

### URL-Only Restart (when jobs disappearing)
```bash
# Fix job disappearing issue
./update_ngrok_urls.sh
git push  # Sync to RunPod
```

## 📡 RunPod GPU Instance Management

### Setting Up New GPU Instance

1. **Spin up RunPod instance** with NVIDIA drivers
2. **SSH into instance:**
   ```bash
   ssh <instance-id>@ssh.runpod.io -i ~/.ssh/id_ed25519
   ```

3. **Complete setup with one command:**
   ```bash
   cd /workspace
   # Download and run setup script (handles everything)
   curl -O https://raw.githubusercontent.com/nishantraghuvanshi/nebula-aether/moksh/setup_runpod.sh
   chmod +x setup_runpod.sh
   ./setup_runpod.sh
   ```

   **What `setup_runpod.sh` does:**
   - Installs system dependencies and Rust
   - Clones/updates repository with latest ngrok URLs
   - Builds the agent
   - Sets up cargo environment permanently
   - Tests GPU detection

4. **Start the agent:**
   ```bash
   cd /workspace/nebula-aether/apps/agent
   cargo run --release  # No need to source cargo env anymore!
   ```

### Updating Existing GPU Instance
```bash
# SSH into RunPod
ssh <instance-id>@ssh.runpod.io -i ~/.ssh/id_ed25519

cd /workspace/nebula-aether

# Method 1: Quick update (if setup already done)
git pull && cargo run --release

# Method 2: Full re-setup (if instance restarted)
./setup_runpod.sh
cd apps/agent && cargo run --release
```

### Managing Multiple GPU Instances
- Each instance runs independently
- All connect to the same local NATS/HTTP endpoints
- GPU IDs are auto-assigned (gpu-0, gpu-1, etc.)
- Monitor all instances from single dashboard

## 🔧 Automation Scripts

### Create Update Script
```bash
cat > scripts/update_ngrok_urls.sh << 'EOF'
#!/bin/bash
set -e

echo "🔄 Updating ngrok URLs..."

# Wait for ngrok to start
sleep 5

# Get URLs
NATS_URL=$(curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[] | select(.name=="nats") | .public_url')
HTTP_URL=$(curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[] | select(.name=="orchestrator") | .public_url')

if [[ "$NATS_URL" == "null" || "$HTTP_URL" == "null" ]]; then
    echo "❌ Failed to get ngrok URLs. Is ngrok running?"
    exit 1
fi

echo "📡 NATS: $NATS_URL"
echo "🌐 HTTP: $HTTP_URL"

# Update files
sed -i '' "s|nats://0.tcp.in.ngrok.io:[0-9]*|${NATS_URL}|g" apps/orchestrator/main.go
sed -i '' "s|nats://0.tcp.in.ngrok.io:[0-9]*|${NATS_URL}|g" apps/agent/src/main.rs
sed -i '' "s|https://[a-z0-9]*.ngrok-free.app|${HTTP_URL}|g" apps/agent/src/main.rs
sed -i '' "s|nats://0.tcp.in.ngrok.io:[0-9]*|${NATS_URL}|g" setup_runpod.sh
sed -i '' "s|https://[a-z0-9]*.ngrok-free.app|${HTTP_URL}|g" setup_runpod.sh

echo "✅ URLs updated in all files"
EOF

chmod +x scripts/update_ngrok_urls.sh
```

### Create Service Start Script
```bash
cat > scripts/start_services.sh << 'EOF'
#!/bin/bash
set -e

echo "🚀 Starting Nebula Aether services..."

# Start orchestrator
cd apps/orchestrator
echo "Starting orchestrator..."
go run . &
ORCHESTRATOR_PID=$!
cd ../..

# Start dashboard
cd apps/dashboard
echo "Starting dashboard..."
npm run dev &
DASHBOARD_PID=$!
cd ../..

# Save PIDs
echo $ORCHESTRATOR_PID > .orchestrator.pid
echo $DASHBOARD_PID > .dashboard.pid

echo "✅ Services started!"
echo "📊 Dashboard: http://localhost:3000"
echo "🔌 API: http://localhost:8080"
echo "📄 PIDs saved to .orchestrator.pid and .dashboard.pid"
EOF

chmod +x scripts/start_services.sh
```

### Create Complete Startup Script
```bash
cat > scripts/startup.sh << 'EOF'
#!/bin/bash
set -e

echo "🌟 Starting Nebula Aether System..."

# Kill existing processes
echo "🧹 Cleaning up existing processes..."
pkill -f "go run" 2>/dev/null || true
pkill -f "npm run dev" 2>/dev/null || true
pkill ngrok 2>/dev/null || true

# Start infrastructure
echo "🏗️ Starting infrastructure..."
docker compose up -d

# Start ngrok
echo "📡 Starting ngrok tunnels..."
ngrok start --all &
sleep 5

# Update URLs
echo "🔄 Updating ngrok URLs..."
./scripts/update_ngrok_urls.sh

# Start services
echo "🚀 Starting application services..."
./scripts/start_services.sh

echo "✅ System started successfully!"
echo "📊 Dashboard: http://localhost:3000"
echo "🎯 Next: Start GPU agents on RunPod instances"
EOF

chmod +x scripts/startup.sh
```

## 📋 Daily Operations Checklist

### Starting Work Session
- [ ] Run `./startup.sh`
- [ ] Verify dashboard loads at http://localhost:3000
- [ ] Check GPU instances show up in dashboard
- [ ] Test job submission

### Adding New GPU Instance
- [ ] Spin up RunPod instance
- [ ] SSH in and run: `./setup_runpod.sh`
- [ ] Start agent: `cargo run --release`
- [ ] Verify GPU appears in dashboard

### Troubleshooting Workflow
1. **Jobs disappearing?** → Run `./update_ngrok_urls.sh && git push`, then `git pull && cargo run --release` on RunPod
2. **Agent won't connect?** → Check ngrok tunnels with `curl -s http://localhost:4040/api/tunnels`
3. **Dashboard empty?** → Run `./start_services.sh` to restart local services
4. **Ngrok errors?** → Run `./stop_system.sh && ./startup.sh` for clean restart
5. **Cargo command not found?** → Run `./setup_runpod.sh` on RunPod (sets up environment permanently)

## 🔍 Monitoring Commands

```bash
# Check running processes
ps aux | grep -E "(go run|npm run dev|ngrok)" | grep -v grep

# Check Docker services
docker compose ps

# Check ngrok tunnels
curl -s http://localhost:4040/api/tunnels | jq '.tunnels[] | {name: .name, url: .public_url}'

# Test API endpoints
curl -s "http://localhost:8080/poll?gpu_id=test"
curl -s http://localhost:3000 > /dev/null && echo "Dashboard OK" || echo "Dashboard down"

# Monitor logs
tail -f logs/orchestrator.log
tail -f logs/dashboard.log
```

## 🚨 Common Issues & Solutions

### Issue: Ngrok URLs Change on Restart
**Solution**: Use the update script after every restart, then push changes for RunPod to pull.

### Issue: Port Already in Use
**Solution**:
```bash
# Find and kill process using port
lsof -ti:8080 | xargs kill -9
lsof -ti:3000 | xargs kill -9
```

### Issue: RunPod Agent Won't Connect
**Solutions**:
1. Check if ngrok tunnels are active
2. Verify URLs in agent code match current ngrok URLs
3. Test endpoints: `curl "https://your-ngrok-url.ngrok-free.app/poll?gpu_id=test"`

### Issue: Jobs Not Executing
**Solutions**:
1. Check agent HTTP polling errors
2. Verify orchestrator API is responding
3. Check job queue in dashboard
4. Review orchestrator logs for job assignment

## 📊 System Health Checks

Create a health check script:
```bash
cat > scripts/health_check.sh << 'EOF'
#!/bin/bash

echo "🏥 Nebula Aether Health Check"
echo "============================="

# Check Docker services
echo "📦 Docker Services:"
docker compose ps --format "table {{.Names}}\t{{.Status}}"

# Check ngrok
echo -e "\n📡 Ngrok Tunnels:"
curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[] | "\(.name): \(.public_url)"' 2>/dev/null || echo "❌ Ngrok not responding"

# Check application services
echo -e "\n🚀 Application Services:"
curl -s http://localhost:3000 > /dev/null && echo "✅ Dashboard: http://localhost:3000" || echo "❌ Dashboard down"
curl -s "http://localhost:8080/poll?gpu_id=test" > /dev/null && echo "✅ Orchestrator API" || echo "❌ Orchestrator down"

# Check process status
echo -e "\n⚙️ Process Status:"
pgrep -f "go run" > /dev/null && echo "✅ Orchestrator process running" || echo "❌ Orchestrator process stopped"
pgrep -f "npm run dev" > /dev/null && echo "✅ Dashboard process running" || echo "❌ Dashboard process stopped"
pgrep ngrok > /dev/null && echo "✅ Ngrok running" || echo "❌ Ngrok stopped"

echo -e "\n📋 Summary:"
echo "Run './scripts/startup.sh' to start all services"
echo "Run 'git pull && cargo run --release' on RunPod instances to update agents"
EOF

chmod +x scripts/health_check.sh
```

This guide covers the complete operational workflow for your distributed GPU orchestration system. The key insight is automating the ngrok URL updates to minimize manual intervention.