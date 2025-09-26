# Nebula Aether - Distributed GPU Orchestration System
## Comprehensive System Overview & Data Flow Analysis

---

## 🎯 System Purpose

Nebula Aether is a **self-improving AI-powered distributed GPU orchestration platform** that allows you to:
- Monitor GPU telemetry in real-time from remote cloud instances (13 enhanced telemetry fields)
- Schedule and execute AI/ML jobs with intelligent resource conflict detection
- Provide a unified dashboard for cluster management with comprehensive logging
- Optimize job placement using AI-powered scheduling with A/B testing and continuous learning
- Prevent job kills through intelligent queuing and resource reservation systems

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LOCAL MACHINE (Mac)                         │
├─────────────────────┬───────────────────┬───────────────────────────┤
│   Dashboard:3000    │  Orchestrator:8080│     Infrastructure        │
│   (Next.js/React)   │      (Go)         │                           │
│   - Web UI          │   - Smart Queue   │  • NATS:4222 (Docker)    │
│   - Real-time data  │   - Resource Track│  • TimescaleDB:5432       │
│   - Job submission  │   - Enhanced Log  │  • AI Core:8000 (Python) │
│                     │   - AI integration│  • ngrok tunnels          │
└─────────────────────┴───────────────────┴───────────────────────────┘
                               │
                        ngrok tunnels
                      (HTTP + TCP/NATS)
                               │
┌─────────────────────────────────────────────────────────────────────┐
│                    RUNPOD GPU INSTANCES (Linux)                     │
├─────────────────────────────────────────────────────────────────────┤
│                    Enhanced Rust Agent Process                     │
│   • 13-Field GPU Telemetry Collection (NVML)                      │
│   • Performance Metrics Extraction (20+ metrics)                  │
│   • Smart Job Execution Engine                                    │
│   • HTTP Polling with AI-Driven Assignment                        │
│   • NATS Publishing for Real-time Telemetry                       │
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
        H[AI Core<br/>Python:8000<br/>XGBoost Models<br/>A/B Testing<br/>Smart Scheduling]
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
| **Dashboard** | Next.js 15, React 19, TypeScript | 3000 | Web UI for monitoring and job submission |
| **Orchestrator** | Go, Enhanced Logging, Connection Pool | 8080 | AI-powered job scheduling, resource tracking, comprehensive logging |
| **AI Core** | Python, FastAPI, XGBoost, A/B Testing | 8000 | Intelligent GPU selection, continuous learning, dual-mode training |
| **Message Bus** | NATS (Docker) | 4222 | Real-time telemetry streaming (13 fields) |
| **Database** | TimescaleDB (Docker), Connection Pool | 5432 | Time-series GPU metrics + job performance data |
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

**Enhanced Collected Metrics** (13 data points per GPU):
- **Identity**: `gpu_name`
- **Performance**: `utilization_gpu`, `utilization_memory_controller`, `performance_state`
- **Clocks**: `clock_gpu_mhz`, `clock_mem_mhz`
- **Memory**: `memory_used_mb`, `memory_total_mb`
- **Thermal/Power**: `temperature_c`, `power_draw_w`, `throttling_reasons`

**Performance Data Collection** (20+ metrics per job):
- **Core Metrics**: `throughput`, `completion_time_sec`, `samples_per_second`, `accuracy`
- **Resource Efficiency**: `memory_efficiency`, `computational_efficiency`, `peak_memory_usage_mb`
- **Quality Metrics**: `error_rate`, `convergence_achieved`, `quality_score`
- **Derived Scores**: `performance_score`, `resource_efficiency`, `thermal_impact`, `power_efficiency`, `reliability_score`

### **4. Job Submission & Execution Flow**

#### **Dashboard → Orchestrator**
```javascript
// User clicks "Submit Job" in dashboard
POST /submit { "id": "gpu-training-basic" }
```

#### **Orchestrator → AI Core (Enhanced)**
```go
// Orchestrator consults AI for intelligent scheduling
POST localhost:8000/predict {
  "candidates": [gpu_states_with_projected_resources...],
  "job_type": "training",
  "job_requirements": {
    "min_memory_mb": 1024,
    "expected_gpu_util": 70,
    "priority": "high",
    "compute_intensity": "compute"
  }
}

// Enhanced Response with Scheduling Intelligence
{
  "best_gpu_id": "gpu-0",
  "scheduling_decision": "assign_now|queue_short|queue_long",
  "estimated_wait_time": 180,
  "scheduling_reason": "Memory sufficient, thermal headroom available",
  "resource_availability": {...}
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
├── logs/                          # Enhanced logging system (auto-generated)
│   ├── job_flow_*.log            # Job lifecycle tracking
│   ├── ai_decisions_*.log        # AI scheduling decisions
│   ├── resources_*.log           # GPU resource management
│   └── ai_predictions_*.log      # AI Core prediction logs
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

## ✅ Recent Major Enhancements

### **AI-Powered Intelligent Scheduling**
1. **Resource Conflict Detection**: Memory, compute, and thermal conflict analysis
2. **Smart Queuing Decisions**: `assign_now`, `queue_short`, `queue_long` with reasoning
3. **Resource Reservation System**: Atomic job assignment with resource tracking
4. **A/B Testing Pipeline**: Continuous model improvement with 20% testing traffic

### **Comprehensive Logging System**
1. **Job Flow Tracking**: Complete lifecycle from submission to completion
2. **AI Decision Logging**: Detailed GPU selection and scheduling reasoning
3. **Resource Tracking**: Real-time resource reservations and releases
4. **Error Analysis**: Structured logging for debugging job kill issues

### **Enhanced Database Architecture**
1. **Connection Pooling**: Eliminates "conn busy" errors with 10-connection pool
2. **Performance Data Storage**: 20+ metrics per job for AI training
3. **Training Data Pipeline**: Automatic feature/label generation for ML models
4. **A/B Testing Metrics**: Model performance tracking and auto-promotion

## 🔍 Remaining System Limitations

### **Known Issues**
1. **ngrok URL Changes**: Free tier causes job failures when URLs change
2. **GPU Agent Dependencies**: Requires stable network for real-time communication

### **System Dependencies**
- **Local**: Docker, Go, Node.js, ngrok account, Python 3.11+
- **RunPod**: NVIDIA drivers, Rust toolchain, Python 3, git access
- **Network**: Stable internet for tunneling and real-time updates
- **AI Models**: Pre-trained XGBoost models for GPU selection (included)

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

## 📈 Enhanced Performance & Monitoring

### **Real-time Metrics (13 GPU fields)**
- Enhanced GPU telemetry: utilization, memory, temperature, clocks, throttling
- Job execution status with performance metrics
- Resource availability and conflict detection
- AI scheduling decisions and reasoning

### **Comprehensive Logging (New)**
- **Job Flow Logs**: Submission → Assignment → Execution → Completion
- **AI Decision Logs**: GPU evaluation, selection reasoning, scheduling decisions
- **Resource Tracking Logs**: Memory/compute reservations, releases, conflicts
- **Performance Analysis**: 20+ metrics per job for continuous AI improvement

### **Enhanced Data Persistence**
- **GPU Telemetry**: 13-field enhanced schema in TimescaleDB
- **Job Performance**: Comprehensive metrics for AI training (20+ fields)
- **Training Data**: Automated feature/label generation for ML pipeline
- **Model Versions**: A/B testing statistics and auto-promotion tracking
- **Debug Logs**: Structured JSON logs for job kill issue analysis

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

## 🎯 Advanced Capabilities

### **Intelligent Job Kill Prevention**
- **Resource Conflict Detection**: Prevents oversubscription before assignment
- **Smart Queuing**: AI decides optimal wait times based on resource availability
- **Atomic Assignment**: Race condition prevention with resource reservation
- **Comprehensive Logging**: Complete visibility into job kill root causes

### **Continuous AI Improvement**
- **A/B Testing**: 20% traffic tests new models, 80% uses proven models
- **Auto-Promotion**: Models achieving 85%+ accuracy become active
- **Performance Tracking**: 20+ metrics per job feed back into training
- **Safe Rollback**: Automatic reversion for underperforming models

### **Production-Grade Monitoring**
- **Structured Logging**: JSON logs for programmatic analysis
- **Resource Tracking**: Real-time GPU memory/compute utilization
- **Performance Analytics**: Job success rates, throughput, efficiency
- **Debug Capabilities**: Complete job lifecycle traceability

---

This system enables **self-improving distributed GPU orchestration** with AI-powered scheduling, intelligent job kill prevention, comprehensive logging, and continuous learning capabilities through advanced machine learning pipelines.