# Aether GPU Telemetry and Scheduling System

A comprehensive GPU telemetry collection and AI-powered job scheduling system built with Rust, Go, Python, and Next.js.

## 🏗️ Architecture

### System Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GPU Hardware  │───▶│  Rust Agent     │───▶│      NATS       │
│   (NVML)        │    │  (Telemetry)    │    │  (Message Bus)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Next.js       │◀───│  Go Orchestrator│◀───│   TimescaleDB   │
│   Dashboard     │    │  (Scheduler)    │    │  (Time Series)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │  Python AI Core │
                       │  (XGBoost ML)   │
                       └─────────────────┘
```

### Component Details

#### 1. **Rust Telemetry Agent** (`apps/agent/`)
- **Purpose**: Collects real-time GPU telemetry data
- **Technology**: Rust with NVML wrapper
- **Features**:
  - Multi-GPU support with individual telemetry streams
  - Comprehensive metrics (temperature, memory, utilization, power, clocks)
  - NATS message publishing
  - Mock mode for macOS development

#### 2. **Go Orchestrator** (`apps/orchestrator/`)
- **Purpose**: Central coordination and job scheduling
- **Technology**: Go with NATS and PostgreSQL drivers
- **Features**:
  - Job queue management
  - AI-powered GPU selection
  - WebSocket API for dashboard
  - Database integration
  - Multi-GPU cluster state management

#### 3. **Python AI Core** (`apps/ai-core/`)
- **Purpose**: Machine learning-based GPU placement decisions
- **Technology**: Python with XGBoost and FastAPI
- **Features**:
  - XGBoost model for optimal GPU selection
  - Multi-GPU candidate evaluation
  - Real-time prediction API
  - Synthetic data generation for training

#### 4. **Next.js Dashboard** (`apps/dashboard/`)
- **Purpose**: Real-time monitoring and visualization
- **Technology**: Next.js with TypeScript
- **Features**:
  - Multi-GPU visualization
  - Real-time telemetry display
  - Anomaly detection alerts
  - Carbon intensity monitoring
  - WebSocket-based updates

#### 5. **Infrastructure**
- **NATS**: High-performance message broker for telemetry
- **TimescaleDB**: Time-series database for historical data storage

## 🚀 Quick Start

### Prerequisites
- macOS (tested on macOS 24.5.0)/linux
- Docker Desktop
- Rust (via rustup)
- Go 1.19+
- Node.js 18+
- Conda/Miniconda

### One-Command Setup

```bash
# Clone and setup everything
git clone <your-repo-url>
cd nebula/project
./setup.sh
```

### Access Points
- **Dashboard**: http://localhost:3000
- **Orchestrator API**: http://localhost:8080
- **AI Core API**: http://localhost:8000
- **Database**: postgres://aether:aether@localhost:5432/aether

## 📊 Data Flow

### Telemetry Collection
1. **GPU Hardware** → **Rust Agent** (via NVML)
2. **Rust Agent** → **NATS** (publishes to `aether.telemetry.gpu-{id}`)
3. **NATS** → **Go Orchestrator** (subscribes to `aether.telemetry.*`)
4. **Go Orchestrator** → **TimescaleDB** (stores historical data)

### Job Scheduling
1. **Job Submission** → **Go Orchestrator** (via HTTP API)
2. **Go Orchestrator** → **Python AI Core** (sends GPU candidates)
3. **Python AI Core** → **Go Orchestrator** (returns best GPU ID)
4. **Go Orchestrator** → **GPU Agent** (via NATS commands)

### Dashboard Updates
1. **Go Orchestrator** → **Next.js Dashboard** (via WebSocket)
2. **Dashboard** → **User** (real-time visualization)

## 🛠️ Management Scripts

### Setup and Restart
```bash
# First-time setup (installs everything)
./setup.sh

# Quick restart for existing setup
./restart.sh

# Stop all services
./stop.sh
```

### Testing
```bash
# Comprehensive system test
./test.sh
```

## 📈 Telemetry Data

### GPU Metrics Collected
- **Temperature**: GPU core temperature
- **Memory**: Used/total memory in MB
- **Utilization**: GPU and memory controller utilization %
- **Power**: Current power draw in watts
- **Clocks**: GPU and memory clock speeds
- **Performance State**: Current performance state
- **Throttling**: Throttling reasons and flags

### Data Storage
- **Format**: Time-series data in TimescaleDB
- **Retention**: Configurable based on needs
- **Indexing**: Optimized for time-based queries
- **Partitioning**: Automatic time-based partitioning

## 🤖 AI-Powered Scheduling

### Machine Learning Model
- **Algorithm**: XGBoost Classifier
- **Features**: Temperature, memory usage, utilization, power draw, job type
- **Output**: Best GPU selection from candidates
- **Training**: Synthetic data generation with realistic patterns

### Scheduling Logic
1. Collect current state of all GPUs
2. Send candidates to AI Core for evaluation
3. Select best GPU based on ML prediction
4. Execute job on selected GPU
5. Monitor and adjust as needed

## 🔧 Configuration

### Environment Variables
- `NATS_URL`: NATS connection string (default: nats://localhost:4222)
- `DATABASE_URL`: PostgreSQL connection string
- `AI_CORE_URL`: AI Core API endpoint (default: http://localhost:8000)

### Customization Points
- **Anomaly Detection**: Modify thresholds in `orchestrator/main.go`
- **Telemetry Frequency**: Adjust interval in `agent/src/main.rs`
- **Dashboard Styling**: Update `dashboard/app/page.tsx`
- **AI Model**: Retrain with new data in `ai-core/train.py`

## 🐛 Troubleshooting

### Common Issues
1. **Docker not running**: Start Docker Desktop
2. **Port conflicts**: Check what's using ports 3000, 8000, 8080
3. **Conda environment**: Recreate with `conda env remove -n aether-ai`
4. **Database connection**: Restart TimescaleDB container

### Logs
- AI Core: `aether/apps/ai-core/ai-core.log`
- Agent: `aether/apps/agent/agent.log`
- Orchestrator: `aether/apps/orchestrator/orchestrator.log`
- Dashboard: `aether/dashboard.log`

## 📁 Project Structure

```
aether/
├── apps/
│   ├── agent/           # Rust telemetry agent
│   ├── orchestrator/    # Go coordination service
│   ├── ai-core/         # Python AI/ML service
│   └── dashboard/       # Next.js monitoring UI
├── docker-compose.yml   # Infrastructure services
├── package.json         # Dashboard dependencies
└── README.md           # This file
```

---

**Built for efficient GPU resource management and intelligent job scheduling**