I# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Nebula Aether is a **self-improving AI-powered distributed GPU orchestration system** that combines real-time monitoring, intelligent job scheduling, and continuous machine learning across remote GPU instances. The system features a **dual-mode AI learning architecture** where normal operations continue uninterrupted while performance data is collected to continuously retrain and improve AI models.

### Key Features
- **🤖 AI-Powered Job Assignment**: Uses XGBoost models to intelligently assign jobs to optimal GPUs
- **🔄 Dual-Mode Learning**: Simultaneous normal operations and training data collection
- **📊 Comprehensive Performance Tracking**: 20+ performance metrics per job type
- **🧪 A/B Testing**: Safe deployment of new models with automatic promotion/rollback
- **⚡ Real-time Telemetry**: 13 GPU telemetry fields with sub-second updates
- **🎯 Continuous Improvement**: Models retrain every 15 minutes with fresh performance data

## Build and Development Commands

### Main Commands
- `npm run dev` - Start all services in development mode (uses Turbo monorepo)
- `npm run build` - Build all apps and packages
- `npm run lint` - Run linting across all apps
- `npm run check-types` - TypeScript type checking across all apps

### System Management Scripts
- `./startup.sh` - Complete system startup (Docker services, ngrok tunnels, all apps)
- `./start_services.sh` - Start only application services (orchestrator + dashboard)
- `./stop_system.sh` - Stop all services and infrastructure
- `./update_ngrok_urls.sh` - Update ngrok tunnel URLs in all files
- `./setup_runpod.sh` - Setup and deploy agent on RunPod GPU instances
- `python auto_job_submitter.py` - Automated training data generation (aggressive job submission)

### Individual App Commands
- **Dashboard**: `cd apps/dashboard && npm run dev`
- **Orchestrator**: `cd apps/orchestrator && go run .`
- **Agent**: `cd apps/agent && cargo run --release`
- **AI Core**: `cd apps/ai-core && python main.py`

### Testing & Validation
- `./test.sh` - Comprehensive system testing (API health, job submission, AI predictions)
- `./submit_job.sh` - Command-line job submission with batch support
- `./validate_upgrade.sh` - Validate dual-mode AI system functionality
- `./test_gpu_id_flow.sh` - Test GPU ID integration across all components

## Architecture Components

### Core Applications (`apps/`)

1. **Dashboard** (`apps/dashboard/`)
   - Next.js 15 + React 19 + TypeScript
   - Real-time GPU monitoring via WebSocket
   - Job submission interface
   - Port: 3000

2. **Orchestrator** (`apps/orchestrator/`)
   - Go service with NATS and TimescaleDB integration
   - **AI-powered job assignment** using machine learning models
   - **Performance data storage** for continuous learning
   - WebSocket API for dashboard updates
   - Port: 8080

3. **Agent** (`apps/agent/`)
   - Rust application with **enhanced NVML telemetry** (13 fields)
   - **Performance metrics extraction** for 10+ job types
   - **Intelligent job execution** with comprehensive monitoring
   - HTTP polling for jobs, NATS publishing for telemetry
   - Deployed on remote RunPod GPU instances

4. **AI Core** (`apps/ai-core/`)
   - Python FastAPI service with **dual-mode learning pipeline**
   - **6 specialized XGBoost models** with A/B testing and auto-promotion
   - **Continuous retraining** every 15 minutes with real performance data
   - GPU selection optimization and model versioning
   - Port: 8000

### Infrastructure Services

- **NATS**: Message broker for real-time telemetry streaming (port 4222)
- **TimescaleDB**: Time-series database with **enhanced schema**:
  - `gpu_telemetry` - 13 telemetry fields (vs original 5)
  - `job_performance` - Comprehensive performance tracking
  - `training_data` - AI model training dataset
  - `model_performance` - A/B testing metrics
  - `model_deployments` - Version control and rollback
- **ngrok**: Tunneling service to expose local services to remote GPU instances

## Data Flow Architecture

### Core Data Flows
1. **Enhanced Telemetry**: GPU → NVML → Rust Agent → NATS → Orchestrator → TimescaleDB (13 fields)
2. **AI-Powered Job Assignment**:
   - Dashboard → Orchestrator → Job Queue
   - GPU polls → Orchestrator → **AI Core** (evaluates all GPUs) → Optimal GPU selection
   - Job executes → **Performance metrics extracted** → Training data generated
3. **Real-time Monitoring**: All components → Orchestrator → Dashboard (WebSocket)

### Dual-Mode Learning Flow
4. **Performance Collection**: Job execution → Metrics extraction → job_performance table
5. **Training Data Generation**: Performance data → Features + Labels → training_data table
6. **Model Retraining**: Training pipeline → New model versions → A/B testing → Auto-promotion
7. **Continuous Improvement**: Better models → Better GPU assignments → Higher performance

## Key Architecture Patterns

### Hybrid Local/Remote Architecture
- Local services (Mac): Dashboard, Orchestrator, NATS, TimescaleDB
- Remote services (RunPod): Rust agents on GPU instances
- Communication via ngrok tunnels (HTTP + TCP)

### Multi-Technology Stack
- Frontend: Next.js with TypeScript
- Backend API: Go with WebSocket support
- GPU Agents: Rust with async tokio runtime
- AI/ML: Python with XGBoost
- Messaging: NATS for pub/sub
- Database: TimescaleDB for time-series data

### Intelligent Job Execution Model
- **HTTP polling** (not WebSocket) with AI-powered GPU selection
- **Smart assignment**: Only optimal GPU (per AI prediction) gets each job
- **Performance tracking**: 20+ metrics extracted per job type
- **Dual-mode operation**: Normal execution + training data collection
- Python subprocess execution with comprehensive monitoring

### AI Learning Pipeline
- **Model versioning**: Timestamp-based versions with rollback capability
- **A/B testing**: 20% traffic to new models, 80% to proven models
- **Auto-promotion**: Models achieving 85%+ accuracy become active
- **Continuous retraining**: Every 15 minutes with fresh performance data
- **Safe deployments**: Automatic rollback for underperforming models

## AI Model Architecture & Pipeline Details

### Six Specialized AI Models

The system employs **6 specialized XGBoost regression models**, each optimized for specific workload categories:

1. **`training_model`** - Neural network training, ML model development
   - **Job Types**: `neural-network-training`, `llm-finetuning-simulation`
   - **Characteristics**: High memory usage, sustained GPU utilization (70-80%)
   - **Optimization Focus**: Memory efficiency, thermal management, long-duration stability

2. **`inference_model`** - Model serving, batch inference
   - **Job Types**: `image-inference-batch`, real-time inference workloads
   - **Characteristics**: Moderate memory, burst utilization patterns (60-70%)
   - **Optimization Focus**: Latency optimization, throughput maximization

3. **`compute_model`** - Heavy computational workloads
   - **Job Types**: `matrix-multiply-heavy`, `video-encoding-benchmark`, `mining`, `encoding`
   - **Characteristics**: Maximum GPU utilization (85-95%), high power draw
   - **Optimization Focus**: Raw compute performance, power efficiency

4. **`general_model`** - General-purpose workloads (fallback)
   - **Job Types**: `monte-carlo-simulation`, `ray-tracing-benchmark`, `protein-folding-simulation`, `analysis`, `rendering`, `research`, `development`
   - **Characteristics**: Variable utilization (75-90%), diverse resource patterns
   - **Optimization Focus**: Balanced resource utilization, workload flexibility

5. **`memory_model`** - Memory-intensive operations
   - **Job Types**: `memory-stress-test`, large dataset processing
   - **Characteristics**: High memory utilization, moderate GPU usage (30-50%)
   - **Optimization Focus**: Memory bandwidth, allocation efficiency

6. **`anomaly_detector`** - System health and anomaly detection
   - **Job Types**: Continuous monitoring, outlier detection
   - **Characteristics**: Low resource usage, continuous operation
   - **Optimization Focus**: System stability, early warning detection

### Feature Engineering Pipeline (22+ Features)

Each prediction uses a **comprehensive feature vector** combining raw telemetry with derived metrics:

#### Core Telemetry Features (13 fields)
```python
# Raw GPU metrics from NVML
- utilization_gpu              # Current GPU utilization %
- utilization_memory_controller # Memory controller utilization %
- gpu_temp (temperature_c)     # Current temperature °C
- power_draw_w                 # Current power consumption watts
- gpu_mem_used, gpu_mem_total  # Memory usage in MB
- clock_gpu_mhz, clock_mem_mhz # Current clock speeds
- performance_state            # P-state (P0-P12)
- throttling_reasons           # Active throttling conditions
- gpu_name, gpu_id            # Hardware identification
```

#### Derived Intelligence Features (9+ fields)
```python
# Calculated performance indicators
- memory_utilization_pct = (gpu_mem_used / gpu_mem_total) * 100
- thermal_headroom = max(83 - gpu_temp, 0)  # °C until thermal limit
- power_per_util = power_draw_w / max(utilization_gpu, 1)
- gpu_clock_ratio = clock_gpu_mhz / 2000.0  # Normalized to base clock
- mem_clock_ratio = clock_mem_mhz / 6000.0  # Normalized to memory clock
- perf_state_numeric = int(performance_state[1:])  # P-state as number
- is_throttling = 1 if active_throttling else 0
- memory_sufficient = 1 if available_memory >= required else 0
- expected_util_match = 1 - abs(current_util - expected_util) / 100
- priority_weight = {'low': 0.5, 'normal': 1.0, 'high': 1.5}[priority]
```

### Continuous Training Pipeline (Dual-Mode Architecture)

#### Training Configuration
```python
training_config = {
    'retrain_interval_hours': 0.25,      # Retrain every 15 minutes
    'min_samples_for_training': 50,      # Minimum data required
    'ab_test_percentage': 20,            # 20% traffic for new models
    'performance_threshold': 0.85,       # 85% accuracy for promotion
}
```

#### Training Data Flow
```
Job Execution → Performance Collection (26 metrics) → Feature Extraction → Training Data Storage
     ↓
Model Retraining (XGBoost) → Validation → Version Creation → A/B Testing → Auto-Promotion
```

#### Training Process (Every 15 Minutes)
1. **Data Collection**: Query last 7 days of `job_performance` joined with `training_data`
2. **Feature Preparation**: Convert JSON features/labels to numpy arrays
3. **Model Training**: XGBoost regressor with 80/20 train/test split
4. **Performance Validation**: MSE calculation, pseudo-R² accuracy scoring
5. **Version Control**: Create timestamp-based versions (`v{unix_timestamp}`)
6. **A/B Deployment**: Save as testing model if accuracy ≥ 85%
7. **Database Recording**: Log deployment in `model_deployments` table

### A/B Testing & Model Management

#### Model Selection Logic
```python
def get_model_and_scaler(job_type: str):
    # 20% chance to use testing model, 80% active model
    if has_testing_model(job_type) and random.randint(1, 100) <= 20:
        return testing_model, testing_scaler, testing_version
    else:
        return active_model, active_scaler, active_version
```

#### Performance Tracking
- **Prediction Counts**: Total predictions per model version
- **Success Rate**: Successful vs failed predictions
- **Average Performance**: Mean performance scores achieved
- **Confidence Metrics**: Model certainty in predictions
- **Promotion Logic**: Auto-promote when testing model outperforms active

#### Model Versioning Schema
```sql
-- model_deployments table
model_name VARCHAR           -- e.g., 'training_model'
model_version VARCHAR        -- e.g., 'v1730234567'
deployment_type VARCHAR      -- 'active', 'ab_test', 'deprecated'
deployment_percentage INT    -- Traffic percentage (20% for testing)
status VARCHAR              -- 'active', 'testing', 'deprecated'
total_predictions INT       -- Prediction count
success_rate FLOAT          -- Performance percentage
```

### Intelligent Scheduling Decision Matrix

#### Multi-Criteria GPU Evaluation
1. **Resource Conflict Analysis**
   - Memory: `(mem_used + required) > mem_total * 0.9`
   - Compute: `(current_util + expected_util) > 85%`
   - Thermal: `temperature > 75°C OR throttling_active`

2. **Scheduling Decisions**
   - **`assign_now`**: No conflicts, immediate assignment
   - **`queue_short`**: Brief wait (30-300s) for resource availability
   - **`queue_long`**: Extended wait (300-600s) for capacity

3. **Risk Assessment**
   - **Thermal Risk**: Temperature proximity to 83°C limit
   - **Memory Risk**: Available memory vs job requirements
   - **Performance Confidence**: Model certainty in prediction

### Current System Performance Metrics

#### Live Model Status
- **Active Models**: 6 specialized models (all v1.0)
- **Training Data**: 133 samples across 10 job types
- **Telemetry Volume**: 18,000+ GPU measurements (last hour: 1,244)
- **Prediction Rate**: Real-time evaluation of all GPU candidates
- **A/B Tests**: Framework active (0 tests currently running)

#### Training Data Distribution
```
Job Type    | Samples | Model Used
------------|---------|-------------
simulation  |    35   | general_model
training    |    18   | training_model
inference   |    16   | inference_model
compute     |    13   | compute_model
encoding    |    12   | compute_model
test        |    10   | general_model
scientific  |     9   | general_model
rendering   |     8   | general_model
llm         |     7   | training_model
memory      |     5   | memory_model
```

#### Automated Training Data Generation
- **Auto Job Submitter**: Aggressive submission (2-15s intervals)
- **Burst Mode**: 30% chance of 3 rapid jobs for pressure testing
- **Weighted Selection**: Favors lighter jobs for frequent data collection
- **Generation Rate**: 20-40 training samples per hour
- **Quality Control**: Automatic data validation and quality scoring

## How the 6 Specialized Models Differ

### Model Training Philosophy & Optimization

Each model is **trained on different job execution patterns** and optimized for distinct workload characteristics:

#### **`training_model` - Long-duration ML workloads**
- **Training Data**: Neural network training, LLM fine-tuning execution patterns
- **Optimization Focus**: Sustained performance over extended periods (5-10+ minutes)
- **Key Priorities**: Memory efficiency, thermal stability, avoiding GPU exhaustion
- **Risk Tolerance**: Conservative thermal management, conservative memory allocation
- **Decision Pattern**: Prefers stable, cool GPUs with ample memory headroom

#### **`inference_model` - Latency-sensitive serving**
- **Training Data**: Batch inference, real-time model serving workloads
- **Optimization Focus**: Quick burst performance, minimal latency
- **Key Priorities**: Fast GPU assignment, minimizing queue wait times
- **Risk Tolerance**: Aggressive memory allocation, high queue sensitivity
- **Decision Pattern**: Favors immediate assignment over resource optimization

#### **`compute_model` - Maximum performance extraction**
- **Training Data**: Matrix operations, video encoding, cryptocurrency mining
- **Optimization Focus**: Raw computational throughput at peak utilization
- **Key Priorities**: High utilization tolerance, power efficiency at peak loads
- **Risk Tolerance**: Aggressive thermal tolerance, aggressive utilization acceptance
- **Decision Pattern**: Maximizes GPU usage even under thermal pressure

#### **`general_model` - Balanced versatility (fallback)**
- **Training Data**: Simulations, rendering, scientific computing, research workloads
- **Optimization Focus**: Adaptability across diverse workload patterns
- **Key Priorities**: Robust performance across mixed job types
- **Risk Tolerance**: Balanced across all dimensions
- **Decision Pattern**: Conservative, balanced approach for unknown workloads

#### **`memory_model` - Memory-intensive operations**
- **Training Data**: Memory stress tests, large dataset processing
- **Optimization Focus**: Memory bandwidth and allocation efficiency
- **Key Priorities**: GPU memory management, avoiding OOM conditions
- **Risk Tolerance**: Critical memory requirements, low utilization tolerance
- **Decision Pattern**: Memory availability is primary constraint

#### **`anomaly_detector` - System health monitoring**
- **Training Data**: Unusual patterns, system failures, performance anomalies
- **Optimization Focus**: Early warning detection, system stability
- **Key Priorities**: Risk prediction, preventing system failures
- **Risk Tolerance**: Conservative across all metrics (stability focus)
- **Decision Pattern**: Prioritizes system health over performance

### Feature Weighting Differences

Each model learns **different feature importance** based on their specialized training data:

```python
# Conceptual feature weights learned by each model

training_model_priorities = {
    'memory_efficiency': 'HIGH',        # Long jobs need sustained memory
    'thermal_headroom': 'HIGH',         # Avoid throttling during training
    'current_utilization': 'MEDIUM',    # Can tolerate some existing load
    'memory_available': 'HIGH',         # Memory leaks in long jobs
    'power_efficiency': 'MEDIUM'        # Extended power draw consideration
}

inference_model_priorities = {
    'latency_indicators': 'HIGH',       # Quick response critical
    'current_utilization': 'LOW',       # Prefer idle GPUs
    'memory_available': 'MEDIUM',       # Batch size dependent
    'thermal_state': 'MEDIUM',          # Burst workloads tolerate heat
    'queue_depth': 'CRITICAL'           # Minimize wait times
}

compute_model_priorities = {
    'raw_performance': 'CRITICAL',      # Maximum throughput
    'power_efficiency': 'HIGH',         # Sustained high loads
    'thermal_headroom': 'MEDIUM',       # Can handle heat better
    'utilization_capacity': 'HIGH',     # Maximize GPU usage
    'clock_speeds': 'HIGH'              # Peak performance states
}

memory_model_priorities = {
    'available_memory': 'CRITICAL',     # Primary constraint
    'memory_bandwidth': 'HIGH',         # Throughput dependent
    'utilization': 'LOW',               # Memory-bound, not compute-bound
    'memory_fragmentation': 'HIGH',     # Large allocation efficiency
    'thermal_impact': 'MEDIUM'          # Memory operations generate heat
}
```

### Scheduling Decision Matrix Differences

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

### Performance Score Calculation Differences

Each model calculates the **0-100 performance score using different algorithms**:

```python
# Simplified scoring formulas (actual ML models are more complex)

def training_model_score(gpu_state, job_requirements):
    score = (
        base_performance *
        memory_efficiency_multiplier *
        thermal_stability_factor *
        sustained_performance_capability
    )
    # Heavily penalizes: High temperature, low memory, thermal throttling
    # Rewards: Cool GPUs, ample memory, stable clocks

def inference_model_score(gpu_state, job_requirements):
    score = (
        latency_factor *
        availability_multiplier *
        burst_capacity_factor *
        queue_position_bonus
    )
    # Heavily penalizes: Queue delays, memory fragmentation, busy GPUs
    # Rewards: Idle GPUs, fast clocks, immediate availability

def compute_model_score(gpu_state, job_requirements):
    score = (
        raw_compute_power *
        utilization_tolerance *
        power_efficiency *
        peak_performance_state
    )
    # Accepts: Higher temperatures, power draw, existing utilization
    # Rewards: Maximum compute capability, high clock speeds
```

### A/B Testing Evolution Patterns

Each model **evolves independently** through specialized A/B testing:

- **Version Management**: `training_model_v1730234567` vs `inference_model_v1730245678`
- **Independent Evolution**: Training model might be v3.2 while inference model is v2.1
- **Specialized Success Metrics**:
  - Training model: Long-term stability, memory efficiency
  - Inference model: Latency reduction, throughput optimization
  - Compute model: Peak utilization achievement, power efficiency
- **Domain-Specific Promotion**: 85% accuracy threshold applied differently per workload type

### Real-World Impact Examples

#### **Gaming/Rendering Workload** (`general_model`)
- Balances visual quality vs thermal management
- Considers frame time consistency over peak FPS
- Decision: "Assign to GPU with balanced thermal/performance profile"

#### **AI Training Workload** (`training_model`)
- Prioritizes memory efficiency for large models
- Avoids thermal throttling that could corrupt training
- Decision: "Queue until cool GPU with 8GB+ memory available"

#### **Real-time Inference** (`inference_model`)
- Minimizes latency even at cost of efficiency
- Prefers GPU switching over waiting
- Decision: "Assign immediately to any available GPU"

#### **Scientific Computing** (`compute_model`)
- Maximizes computational throughput
- Tolerates higher power draw for accuracy
- Decision: "Assign to highest-performance GPU regardless of current load"

#### **Large Dataset Processing** (`memory_model`)
- Memory availability is the primary constraint
- Will wait indefinitely for sufficient memory
- Decision: "Queue long until 12GB+ contiguous memory available"

#### **System Monitoring** (`anomaly_detector`)
- Stability and predictability over performance
- Conservative resource allocation
- Decision: "Assign only to proven-stable GPU with low thermal risk"

This **multi-model architecture** enables Nebula Aether to make specialized, intelligent decisions rather than using a one-size-fits-all approach, resulting in significantly better performance optimization for each distinct workload category.

## Development Workflow

### Local Development
1. Start infrastructure: `docker compose up -d`
2. Start ngrok tunnels: `ngrok start --all`
3. Update tunnel URLs: `./update_ngrok_urls.sh`
4. Install AI Core dependencies: `cd apps/ai-core && pip install -r requirements.txt`
5. Start services: `./start_services.sh` or individual app commands

### RunPod GPU Instance Setup
1. Use `./setup_runpod.sh` for complete environment setup
2. Start agent: `cargo run --release`
3. Agent auto-connects to local services via ngrok

### URL Management
- ngrok URLs change on restart (free tier limitation)
- Use `./update_ngrok_urls.sh` to sync new URLs across all files
- Always `git push` changes for RunPod instances to pull

## Testing Strategy

- System health checks via `./test.sh`
- API endpoint validation
- WebSocket connection testing
- Job submission and execution validation
- AI model prediction testing

## Configuration Files

- `turbo.json` - Monorepo build configuration
- `docker-compose.yml` - Infrastructure services (NATS, TimescaleDB)
- `ngrok.yml` - Tunnel configuration
- Individual `package.json`, `Cargo.toml`, `go.mod` in respective apps

## AI System Control

### Training Pipeline Control
**Note**: The training pipeline runs continuously by default. Environment toggle is not currently implemented.

```bash
# Training pipeline starts automatically with AI Core
# Future implementation for optional control:
# export ENABLE_TRAINING_PIPELINE=true   # Enable dual-mode learning (default)
# export ENABLE_TRAINING_PIPELINE=false  # Disable - uses existing models only
```

### Training Pipeline Endpoints
```bash
# Check training status
curl http://localhost:8000/training/status

# View A/B testing statistics
curl http://localhost:8000/training/ab-stats

# Manual model retraining
curl -X POST http://localhost:8000/training/retrain/training_model

# Promote model version
curl -X POST http://localhost:8000/training/promote/training_model/v123456

# List all model versions
curl http://localhost:8000/training/models

# Reload models after training
curl -X POST http://localhost:8000/training/reload-models
```

### Automated Training Data Generation
```bash
# Run indefinitely for continuous training data (recommended)
python auto_job_submitter.py

# Run for specific duration with custom intervals
python auto_job_submitter.py --hours 2 --interval 30

# Aggressive training mode (faster data collection)
python auto_job_submitter.py --interval 5 --min-interval 2 --max-interval 15

# Custom orchestrator URL
python auto_job_submitter.py --url http://localhost:8080
```

#### Auto Submitter Features
- **Weighted Job Selection**: Balanced distribution across 10 job types
- **Burst Mode**: 30% chance of 3 rapid jobs for pressure testing
- **Adaptive Intervals**: 2-15s submission rates based on system load
- **Real-time Statistics**: Performance tracking and job distribution metrics
- **Quality Control**: Automatic error handling and retry logic

## System Status & Monitoring

### Current AI Implementation
- **✅ AI-Powered Job Assignment**: Active - uses 6 specialized XGBoost models for GPU selection
- **✅ Performance Data Collection**: Every job generates training data (133 samples collected)
- **✅ Continuous Learning**: Models retrain every 15 minutes automatically
- **✅ A/B Testing**: 20% traffic tests new models before promotion (framework active)
- **✅ Enhanced Telemetry**: 13 GPU metrics vs original 5 (18K+ samples collected)
- **✅ Feature Engineering**: 22+ features from raw telemetry + derived metrics
- **✅ Multi-Model Architecture**: Specialized models for training, inference, compute, general, memory, anomaly detection

### How AI Selection Works
1. **Job Request**: GPU polls for job: `GET /poll?gpu_id=hostname:gpu-0`
2. **Model Selection**: Job type → specialized model (training/inference/compute/general/memory/anomaly)
3. **A/B Testing**: 20% chance to use testing model, 80% active model
4. **Feature Engineering**: 13 telemetry fields → 22+ features (thermal, memory, power, clocks)
5. **GPU Evaluation**: All candidates scored using XGBoost regression (0-100 performance score)
6. **Scheduling Logic**: Multi-criteria decision matrix (memory/thermal/compute conflicts)
7. **Selection**: Best GPU chosen with confidence score and scheduling reason
8. **Assignment**: Only optimal GPU receives job assignment
9. **Performance Collection**: 26 execution metrics → training data for continuous improvement
10. **Model Retraining**: Every 15 minutes with fresh performance data

## Common Issues

1. **ngrok URL changes**: Run `./update_ngrok_urls.sh && git push`, then restart agents
2. **AI Core dependencies**: Run `cd apps/ai-core && pip install -r requirements.txt`
3. **Port conflicts**: Use `lsof -ti:PORT | xargs kill -9` to clear ports
4. **Agent connection failures**: Verify ngrok tunnels and URL synchronization
5. **Training pipeline errors**: Check `ENABLE_TRAINING_PIPELINE` environment variable