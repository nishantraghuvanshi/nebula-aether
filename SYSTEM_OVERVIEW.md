# Nebula Aether - Distributed GPU Orchestration System
## Comprehensive System Overview & Data Flow Analysis

---

## 🎯 System Purpose

Nebula Aether is a **distributed GPU orchestration platform** that allows you to:
- Monitor GPU telemetry in real-time from remote cloud instances
- Schedule and execute AI/ML jobs across multiple GPUs
- Provide a unified dashboard for cluster management
- Optimize job placement using AI-powered scheduling

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LOCAL MACHINE (Mac)                         │
├─────────────────────┬───────────────────┬───────────────────────────┤
│   Dashboard:3000    │  Orchestrator:8080│     Infrastructure        │
│   (Next.js/React)   │      (Go)         │                           │
│   - Web UI          │   - Job Queue     │  • NATS:4222 (Docker)    │
│   - Real-time data  │   - GPU coords    │  • TimescaleDB:5432       │
│   - Job submission  │   - AI integration│  • ngrok tunnels          │
└─────────────────────┴───────────────────┴───────────────────────────┘
                               │
                        ngrok tunnels
                      (HTTP + TCP/NATS)
                               │
┌─────────────────────────────────────────────────────────────────────┐
│                    RUNPOD GPU INSTANCES (Linux)                     │
├─────────────────────────────────────────────────────────────────────┤
│                    Rust Agent Process                              │
│   • GPU Telemetry Collection (NVML)                               │
│   • Job Execution Engine                                          │
│   • HTTP Polling for Jobs                                         │
│   • NATS Publishing for Metrics                                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Data Flow Architecture

```mermaid
graph TD
    subgraph "Local Machine (Mac)"
        A[Dashboard<br/>Next.js:3000]
        B[Orchestrator<br/>Go:8080]
        C[NATS<br/>Docker:4222]
        D[TimescaleDB<br/>Docker:5432]
        E[ngrok<br/>Tunnels]
    end

    subgraph "RunPod GPU Cloud"
        F[Rust Agent<br/>NVML + HTTP]
        G[NVIDIA GPU<br/>Hardware]
    end

    subgraph "AI Services"
        H[AI Core<br/>Python:8000<br/>Job Scheduling]
    end

    %% Data Flows
    F -->|GPU Telemetry<br/>JSON via NATS| C
    C -->|Telemetry Stream| B
    B -->|Store Metrics<br/>SQL INSERT| D
    B -->|Real-time Data<br/>WebSocket| A
    A -->|Submit Job<br/>HTTP POST| B
    B -->|GPU Selection<br/>HTTP POST| H
    H -->|Best GPU ID<br/>JSON Response| B
    B -->|Job in Queue<br/>HTTP GET| F
    F -->|Job Status<br/>JSON via NATS| C
    C -->|Status Updates| B
    B -->|Status Stream<br/>WebSocket| A
    F -->|Execute Scripts<br/>Python subprocess| G

    %% Network
    E -->|Expose Local Services| Internet
    Internet -->|HTTP/TCP Tunnels| F
```

---

## 🔧 Technology Stack

### **Local Machine Components**
| Component | Technology | Port | Purpose |
|-----------|------------|------|---------|
| **Dashboard** | Next.js 14, React, TypeScript | 3000 | Web UI for monitoring and job submission |
| **Orchestrator** | Go, Gorilla WebSocket | 8080 | Job scheduling, GPU coordination, API |
| **Message Bus** | NATS (Docker) | 4222 | Real-time telemetry streaming |
| **Database** | TimescaleDB (Docker) | 5432 | Time-series GPU metrics storage |
| **Tunneling** | ngrok | 4040 | Expose local services to cloud |

### **Remote GPU Instances**
| Component | Technology | Purpose |
|-----------|------------|---------|
| **Agent** | Rust, tokio, NVML wrapper | GPU monitoring and job execution |
| **GPU Access** | NVIDIA Management Library (NVML) | Hardware telemetry collection |
| **Job Runtime** | Python subprocess execution | AI/ML workload execution |

---

## 🌊 Complete Data Flow Walkthrough

### **1. System Startup Sequence**
```bash
./startup.sh  # Automated startup script
```
1. **Docker services start**: NATS + TimescaleDB containers
2. **ngrok tunnels launch**: HTTP (port 8080) + TCP (port 4222)
3. **URL synchronization**: Updates agent/orchestrator with new tunnel URLs
4. **Services launch**: Orchestrator (Go) + Dashboard (Next.js)

### **2. GPU Agent Connection Flow**
```rust
// RunPod instance: cargo run --release
```
1. **NVML initialization**: Connect to GPU hardware
2. **NATS connection**: Connect to `tcp://0.tcp.in.ngrok.io:18595`
3. **HTTP polling setup**: Poll `https://xyz.ngrok-free.app/poll?gpu_id=gpu-0`
4. **Telemetry streaming**: Send GPU metrics every 2 seconds

### **3. Telemetry Collection & Storage**
```
GPU Hardware → NVML → Rust Agent → NATS → Orchestrator → TimescaleDB
```

**Collected Metrics** (12 data points per GPU):
- **Identity**: `gpu_name`
- **Performance**: `utilization_gpu`, `utilization_memory_controller`, `performance_state`
- **Clocks**: `clock_gpu_mhz`, `clock_mem_mhz`
- **Memory**: `memory_used_mb`, `memory_total_mb`
- **Thermal/Power**: `temperature_c`, `power_draw_w`, `throttling_reasons`

**Database Schema Issue**: TimescaleDB schema only stores 5 fields but orchestrator tries to insert 12 (causing errors).

### **4. Job Submission & Execution Flow**

#### **Dashboard → Orchestrator**
```javascript
// User clicks "Submit Job" in dashboard
POST /submit { "id": "gpu-training-basic" }
```

#### **Orchestrator → AI Core**
```go
// Orchestrator consults AI for GPU selection
POST localhost:8000/predict {
  "candidates": [gpu_states...],
  "job_type": "training",
  "job_requirements": {...}
}
```

#### **Orchestrator → Agent (HTTP Polling)**
```
Agent polls: GET /poll?gpu_id=gpu-0
Orchestrator responds: { "job": JobExecution, "message": "job assigned" }
```

#### **Agent → Job Execution**
```rust
// Agent executes Python scripts
Command::new("python3")
  .arg("script.py")
  .arg("--device").arg("cuda")
  .spawn()
```

#### **Status Reporting**
```
Agent → NATS → Orchestrator → Dashboard
Job status: started → running → completed/failed
```

---

## 📁 File Structure & Key Components

```
nebula-aether/
├── apps/
│   ├── agent/src/main.rs          # Rust GPU agent (NVML + job execution)
│   ├── orchestrator/main.go       # Go API server + job scheduler
│   ├── dashboard/                 # Next.js web interface
│   └── ai-core/                   # Python ML model for GPU selection
├── demo-jobs/                     # Job definitions and Python scripts
├── docker-compose.yml             # NATS + TimescaleDB containers
├── ngrok.yml                      # Tunnel configuration
├── startup.sh                     # Complete system startup
├── stop_system.sh                 # Clean shutdown
└── setup_runpod.sh               # RunPod instance setup
```

---

## 🚀 Operational Workflow

### **Daily Startup Process**
1. **Local**: `./startup.sh` (starts everything automatically)
2. **RunPod**: SSH into instance → `./setup_runpod.sh` → `cargo run --release`
3. **Verify**: Dashboard at http://localhost:3000 shows connected GPUs

### **Job Execution Process**
1. **Submit**: Select job type in dashboard → click submit
2. **AI Selection**: Orchestrator asks AI which GPU is best
3. **Execution**: Agent polls for job → executes Python script
4. **Monitoring**: Real-time status updates in dashboard

### **ngrok URL Management**
- URLs change on ngrok restart (free tier limitation)
- `./update_ngrok_urls.sh` updates all files automatically
- Must `git push` and `git pull` on RunPod to sync changes

---

## 🔍 Current System Limitations & Issues

### **Known Issues**
1. **Database Schema Mismatch**: TimescaleDB schema missing 7 telemetry fields
2. **ngrok URL Changes**: Free tier causes job failures when URLs change
3. **Mock GPU Pollution**: Previously showed fake GPUs alongside real ones (fixed)

### **System Dependencies**
- **Local**: Docker, Go, Node.js, ngrok account
- **RunPod**: NVIDIA drivers, Rust toolchain, Python 3, git access
- **Network**: Stable internet for tunneling and real-time updates

---

## 🎛️ Key Configuration Points

### **NATS Connection**
```rust
// Agent connects to NATS via ngrok tunnel
let nats_url = "tcp://0.tcp.in.ngrok.io:18595";
```

### **HTTP Polling**
```rust
// Agent polls for jobs via ngrok HTTP tunnel
let orchestrator_url = "https://5f9184d7a785.ngrok-free.app";
```

### **Database Connection**
```go
// Orchestrator connects to local TimescaleDB
dbUrl := "postgres://aether:aether@localhost:5432/aether"
```

---

## 📈 Performance & Monitoring

### **Real-time Metrics**
- GPU utilization, memory usage, temperature
- Job execution status and logs
- System health indicators

### **Data Persistence**
- All GPU telemetry stored in TimescaleDB (time-series)
- Job execution history and status
- RunPod `/workspace` persistence (only directory that survives restarts)

---

## 🛠️ Development & Debugging

### **Local Development**
- Dashboard: `cd apps/dashboard && npm run dev`
- Orchestrator: `cd apps/orchestrator && go run .`
- Database: `docker compose up -d`

### **RunPod Development**
- Setup: `./setup_runpod.sh` (handles environment, builds agent)
- Run: `cargo run --release` (starts telemetry + job polling)
- Debug: Check NATS connection, HTTP polling logs

---

This system enables **distributed GPU compute orchestration** with real-time monitoring, AI-powered job scheduling, and seamless cloud integration through ngrok tunneling.