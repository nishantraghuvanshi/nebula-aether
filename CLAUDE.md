# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Nebula Aether is a **self-improving AI-powered distributed GPU orchestration system** that combines real-time monitoring, intelligent job scheduling, and continuous machine learning across remote GPU instances. The system features a **dual-mode AI learning architecture** where normal operations continue uninterrupted while performance data is collected to continuously retrain and improve AI models.

### Key Features
- **🤖 AI-Powered Job Assignment**: Uses XGBoost models to intelligently assign jobs to optimal GPUs
- **🔄 Dual-Mode Learning**: Simultaneous normal operations and training data collection
- **📊 Comprehensive Performance Tracking**: 20+ performance metrics per job type
- **🧪 A/B Testing**: Safe deployment of new models with automatic promotion/rollback
- **⚡ Real-time Telemetry**: 13 GPU telemetry fields with sub-second updates
- **🎯 Continuous Improvement**: Models retrain every 6 hours with fresh performance data

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
   - **XGBoost models** with A/B testing and auto-promotion
   - **Continuous retraining** every 6 hours with real performance data
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
- **Continuous retraining**: Every 6 hours with fresh performance data
- **Safe deployments**: Automatic rollback for underperforming models

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
```bash
# Enable dual-mode learning (default)
export ENABLE_TRAINING_PIPELINE=true

# Disable - uses existing models only
export ENABLE_TRAINING_PIPELINE=false
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

## System Status & Monitoring

### Current AI Implementation
- **✅ AI-Powered Job Assignment**: Active - uses XGBoost models for GPU selection
- **✅ Performance Data Collection**: Every job generates training data
- **✅ Continuous Learning**: Models retrain every 6 hours automatically
- **✅ A/B Testing**: 20% traffic tests new models before promotion
- **✅ Enhanced Telemetry**: 13 GPU metrics vs original 5

### How AI Selection Works
1. GPU polls for job: `GET /poll?gpu_id=hostname:gpu-0`
2. Orchestrator asks AI Core: Evaluates all available GPUs
3. AI returns optimal GPU based on telemetry + job requirements
4. Only optimal GPU receives the job assignment
5. Performance metrics collected for future model improvement

## Common Issues

1. **ngrok URL changes**: Run `./update_ngrok_urls.sh && git push`, then restart agents
2. **AI Core dependencies**: Run `cd apps/ai-core && pip install -r requirements.txt`
3. **Port conflicts**: Use `lsof -ti:PORT | xargs kill -9` to clear ports
4. **Agent connection failures**: Verify ngrok tunnels and URL synchronization
5. **Training pipeline errors**: Check `ENABLE_TRAINING_PIPELINE` environment variable