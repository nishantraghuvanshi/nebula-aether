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
- **Purpose**: Real-time monitoring and job submission interface
- **Technology**: Next.js with TypeScript
- **Features**:
  - Multi-GPU visualization with dynamic cards
  - Real-time telemetry display
  - Anomaly detection alerts with visual indicators
  - Carbon intensity monitoring
  - Interactive job submission form
  - WebSocket-based real-time updates
  - CORS-enabled API integration

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

### Testing and Job Submission
```bash
# Comprehensive system test
./test.sh

# Submit jobs via command line
./submit_job.sh [job_id] [job_type]
./submit_job.sh --batch training 5    # Submit 5 training jobs
./submit_job.sh --status              # Check system status
./submit_job.sh --help                # Show usage help
```

### Script Details

#### **setup.sh** - Complete System Setup
- Installs system dependencies (Docker, Conda, Go, Node.js, Rust)
- Sets up infrastructure (NATS, TimescaleDB)
- Creates Conda environment and installs Python dependencies
- Trains AI model with synthetic data
- Starts all services and verifies functionality
- **Usage**: `./setup.sh` (first time only)

#### **restart.sh** - Quick Service Restart
- Stops existing services gracefully
- Starts infrastructure containers
- Restarts all application services
- Verifies service health
- **Usage**: `./restart.sh` (for existing setups)

#### **stop.sh** - Graceful Shutdown
- Stops all running services
- Stops Docker containers
- Optionally cleans log files
- **Usage**: `./stop.sh`

#### **test.sh** - Comprehensive Testing
- Tests service health endpoints
- Validates API functionality
- Tests job submission and AI predictions
- Verifies WebSocket connections
- Tests database connectivity
- Performance and error handling tests
- **Usage**: `./test.sh`

#### **submit_job.sh** - Command Line Job Submission
- Submit individual jobs with custom IDs
- Batch job submission for testing
- System status checking
- Color-coded output with error handling
- CORS-compatible with orchestrator
- **Usage**: 
  - `./submit_job.sh` (auto-generated ID)
  - `./submit_job.sh my-job-001 training`
  - `./submit_job.sh --batch inference 10`

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
- `ORCHESTRATOR_URL`: Orchestrator API endpoint (default: http://localhost:8080)

### Customization Points
- **Anomaly Detection**: Modify thresholds in `orchestrator/main.go`
- **Telemetry Frequency**: Adjust interval in `agent/src/main.rs`
- **Dashboard Styling**: Update `dashboard/app/page.tsx`
- **AI Model**: Retrain with new data in `ai-core/train.py`
- **CORS Settings**: Configure in `orchestrator/main.go` corsMiddleware function

## 🐛 Troubleshooting

### Common Issues
1. **Docker not running**: Start Docker Desktop
2. **Port conflicts**: Check what's using ports 3000, 8000, 8080
3. **Conda environment**: Recreate with `conda env remove -n aether-ai`
4. **Database connection**: Restart TimescaleDB container
5. **CORS errors**: Ensure orchestrator is running with updated CORS middleware
6. **Job submission fails**: Check orchestrator logs and verify API endpoints
7. **Dashboard not updating**: Verify WebSocket connection and orchestrator status

### Logs
- AI Core: `aether/apps/ai-core/ai-core.log`
- Agent: `aether/apps/agent/agent.log`
- Orchestrator: `aether/apps/orchestrator/orchestrator.log`
- Dashboard: `aether/dashboard.log`

## 📁 Project Structure

```
project/
├── aether/
│   ├── apps/
│   │   ├── agent/           # Rust telemetry agent
│   │   ├── orchestrator/    # Go coordination service
│   │   ├── ai-core/         # Python AI/ML service
│   │   └── dashboard/       # Next.js monitoring UI
│   ├── docker-compose.yml   # Infrastructure services
│   ├── package.json         # Dashboard dependencies
│   └── README.md           # This file
├── setup.sh                 # Complete system setup script
├── restart.sh               # Quick service restart script
├── stop.sh                  # Graceful shutdown script
├── test.sh                  # Comprehensive testing script
├── submit_job.sh            # Command-line job submission
├── ABSTRACT.md              # Technical project abstract
└── aether.pids              # Process ID tracking (auto-generated)
```

## 🎯 Key Features

### ✅ **Multi-GPU Support**
- Dynamic GPU detection and individual telemetry streams
- Concurrent state management across multiple GPUs
- Scalable architecture supporting unlimited GPU nodes

### ✅ **AI-Powered Scheduling**
- XGBoost-based machine learning model for optimal job placement
- Real-time GPU candidate evaluation
- Intelligent resource allocation based on telemetry data

### ✅ **Real-time Monitoring**
- Live dashboard with WebSocket updates
- Anomaly detection with visual indicators
- Carbon intensity tracking
- Multi-GPU visualization with dynamic cards

### ✅ **Comprehensive Tooling**
- One-command setup with `setup.sh`
- Automated testing with `test.sh`
- Command-line job submission with `submit_job.sh`
- Graceful service management with `restart.sh` and `stop.sh`

### ✅ **Cross-Platform Compatibility**
- NVML integration for NVIDIA GPUs on Linux/Windows
- Mock simulation system for macOS development
- Docker containerization for consistent deployment

### ✅ **Production Ready**
- CORS-enabled API endpoints
- Comprehensive error handling and logging
- Time-series optimized database storage
- High-performance message queuing with NATS

---

**Built for efficient GPU resource management and intelligent job scheduling**