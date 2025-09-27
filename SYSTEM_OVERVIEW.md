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

## 🧠 Six Specialized AI Models Architecture

### **Model Specialization & Training Philosophy**

Nebula Aether employs **6 specialized XGBoost regression models**, each trained on different execution patterns and optimized for distinct workload characteristics:

#### **1. `training_model` - Long-duration ML workloads**
- **Training Data**: Neural network training, LLM fine-tuning execution patterns
- **Optimization Focus**: Sustained performance over extended periods (5-10+ minutes)
- **Key Priorities**: Memory efficiency, thermal stability, avoiding GPU exhaustion
- **Risk Tolerance**: Conservative thermal management, conservative memory allocation
- **Job Types**: `neural-network-training`, `llm-finetuning-simulation`

#### **2. `inference_model` - Latency-sensitive serving**
- **Training Data**: Batch inference, real-time model serving workloads
- **Optimization Focus**: Quick burst performance, minimal latency
- **Key Priorities**: Fast GPU assignment, minimizing queue wait times
- **Risk Tolerance**: Aggressive memory allocation, high queue sensitivity
- **Job Types**: `image-inference-batch`, real-time inference workloads

#### **3. `compute_model` - Maximum performance extraction**
- **Training Data**: Matrix operations, video encoding, cryptocurrency mining
- **Optimization Focus**: Raw computational throughput at peak utilization
- **Key Priorities**: High utilization tolerance, power efficiency at peak loads
- **Risk Tolerance**: Aggressive thermal tolerance, aggressive utilization acceptance
- **Job Types**: `matrix-multiply-heavy`, `video-encoding-benchmark`, `mining`, `encoding`

#### **4. `general_model` - Balanced versatility (fallback)**
- **Training Data**: Simulations, rendering, scientific computing, research workloads
- **Optimization Focus**: Adaptability across diverse workload patterns
- **Key Priorities**: Robust performance across mixed job types
- **Risk Tolerance**: Balanced across all dimensions
- **Job Types**: `monte-carlo-simulation`, `ray-tracing-benchmark`, `protein-folding-simulation`

#### **5. `memory_model` - Memory-intensive operations**
- **Training Data**: Memory stress tests, large dataset processing
- **Optimization Focus**: Memory bandwidth and allocation efficiency
- **Key Priorities**: GPU memory management, avoiding OOM conditions
- **Risk Tolerance**: Critical memory requirements, low utilization tolerance
- **Job Types**: `memory-stress-test`, large dataset processing

#### **6. `anomaly_detector` - System health monitoring**
- **Training Data**: Unusual patterns, system failures, performance anomalies
- **Optimization Focus**: Early warning detection, system stability
- **Key Priorities**: Risk prediction, preventing system failures
- **Risk Tolerance**: Conservative across all metrics (stability focus)
- **Job Types**: Continuous monitoring, outlier detection

### **Feature Engineering Pipeline (22+ Features)**

Each model processes a comprehensive feature vector combining raw telemetry with derived intelligence:

#### **Core Telemetry Features (13 fields)**
```
- utilization_gpu              # Current GPU utilization %
- utilization_memory_controller # Memory controller utilization %
- temperature_c                # Current temperature °C
- power_draw_w                 # Current power consumption watts
- memory_used_mb, memory_total_mb # Memory usage statistics
- clock_gpu_mhz, clock_mem_mhz # Current clock speeds
- performance_state            # P-state (P0-P12)
- throttling_reasons           # Active throttling conditions
- gpu_name, gpu_id            # Hardware identification
```

#### **Derived Intelligence Features (9+ fields)**
```
- memory_utilization_pct = (memory_used / memory_total) * 100
- thermal_headroom = max(83 - temperature, 0)  # °C until thermal limit
- power_per_util = power_draw / max(utilization_gpu, 1)
- gpu_clock_ratio = clock_gpu / 2000.0  # Normalized to base clock
- mem_clock_ratio = clock_mem / 6000.0  # Normalized to memory clock
- perf_state_numeric = int(performance_state[1:])  # P-state as number
- is_throttling = 1 if active_throttling else 0
- memory_sufficient = 1 if available_memory >= required else 0
- priority_weight = {'low': 0.5, 'normal': 1.0, 'high': 1.5}[priority]
```

### **Scheduling Decision Matrix Differences**

Each model makes **different scheduling decisions** for identical GPU states:

**Example Scenario**: GPU at 60% utilization, 70°C, 6GB/8GB memory used

| Model | Decision | Reasoning |
|-------|----------|-----------|
| `training_model` | `queue_short` | "Wait for memory to free up - need sustained allocation" |
| `inference_model` | `assign_now` | "Can burst into available resources quickly" |
| `compute_model` | `assign_now` | "Can effectively utilize remaining 40% capacity" |
| `general_model` | `queue_short` | "Conservative balanced approach for unknown workload" |
| `memory_model` | `queue_long` | "Insufficient memory available - critical constraint" |
| `anomaly_detector` | `queue_short` | "Thermal approaching concern threshold" |

### **Performance Score Calculation Differences**

Each model uses **specialized algorithms** to calculate 0-100 performance scores:

```python
# Conceptual scoring differences (actual ML models are more complex)

training_model_score = (
    base_performance *
    memory_efficiency_multiplier *
    thermal_stability_factor *
    sustained_performance_capability
)
# Heavily penalizes: High temperature, low memory, thermal throttling
# Rewards: Cool GPUs, ample memory, stable clocks

inference_model_score = (
    latency_factor *
    availability_multiplier *
    burst_capacity_factor *
    queue_position_bonus
)
# Heavily penalizes: Queue delays, memory fragmentation, busy GPUs
# Rewards: Idle GPUs, fast clocks, immediate availability

compute_model_score = (
    raw_compute_power *
    utilization_tolerance *
    power_efficiency *
    peak_performance_state
)
# Accepts: Higher temperatures, power draw, existing utilization
# Rewards: Maximum compute capability, high clock speeds
```

### **Continuous Learning & A/B Testing**

#### **Independent Model Evolution**
- **Version Management**: Each model evolves independently (`training_model_v1730234567`)
- **Specialized Metrics**: Domain-specific success criteria per model type
- **A/B Testing**: 20% traffic tests new models, 80% uses proven models
- **Auto-Promotion**: Models achieving 85%+ accuracy become active

#### **Training Pipeline (Every 15 Minutes)**
1. **Data Collection**: Query last 7 days of job performance data
2. **Model Training**: XGBoost regressor with specialized feature weighting
3. **Validation**: Domain-specific accuracy scoring
4. **Version Creation**: Timestamp-based model versioning
5. **A/B Deployment**: Safe testing with automatic rollback

### **Real-World Impact Examples**

#### **AI Training Workload** (`training_model`)
- **Scenario**: Fine-tuning large language model
- **Decision**: "Queue until cool GPU with 8GB+ memory available"
- **Result**: Avoids thermal throttling that could corrupt training

#### **Real-time Inference** (`inference_model`)
- **Scenario**: Live image classification API
- **Decision**: "Assign immediately to any available GPU"
- **Result**: Minimizes latency even at cost of efficiency

#### **Scientific Computing** (`compute_model`)
- **Scenario**: Molecular dynamics simulation
- **Decision**: "Assign to highest-performance GPU regardless of current load"
- **Result**: Maximizes computational throughput for accuracy

#### **Large Dataset Processing** (`memory_model`)
- **Scenario**: Processing 50GB dataset
- **Decision**: "Queue long until 12GB+ contiguous memory available"
- **Result**: Prevents out-of-memory failures

This **multi-model architecture** enables specialized, intelligent decisions rather than one-size-fits-all scheduling, resulting in significantly better performance optimization for each workload category.

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