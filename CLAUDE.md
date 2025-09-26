# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Nebula Aether is a distributed GPU orchestration system that enables real-time monitoring and AI-powered job scheduling across remote GPU instances. The system uses a hybrid architecture with local coordination services and remote GPU agents.

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

### Testing
- `./test.sh` - Comprehensive system testing (API health, job submission, AI predictions)
- `./submit_job.sh` - Command-line job submission with batch support

## Architecture Components

### Core Applications (`apps/`)

1. **Dashboard** (`apps/dashboard/`)
   - Next.js 15 + React 19 + TypeScript
   - Real-time GPU monitoring via WebSocket
   - Job submission interface
   - Port: 3000

2. **Orchestrator** (`apps/orchestrator/`)
   - Go service with NATS and PostgreSQL integration
   - Job queue management and AI-powered GPU selection
   - WebSocket API for dashboard updates
   - Port: 8080

3. **Agent** (`apps/agent/`)
   - Rust application with NVML GPU telemetry collection
   - Job execution engine with Python subprocess handling
   - HTTP polling for job requests, NATS publishing for telemetry
   - Deployed on remote RunPod GPU instances

4. **AI Core** (`apps/ai-core/`)
   - Python FastAPI service with XGBoost ML models
   - GPU selection optimization based on telemetry data
   - Port: 8000

### Infrastructure Services

- **NATS**: Message broker for real-time telemetry streaming (port 4222)
- **TimescaleDB**: Time-series database for GPU metrics storage (port 5432)
- **ngrok**: Tunneling service to expose local services to remote GPU instances

## Data Flow Architecture

1. **Telemetry Flow**: GPU → NVML → Rust Agent → NATS → Orchestrator → TimescaleDB
2. **Job Submission**: Dashboard → Orchestrator → AI Core (GPU selection) → Agent (HTTP polling) → GPU execution
3. **Real-time Updates**: All components → Orchestrator → Dashboard (WebSocket)

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

### Job Execution Model
- HTTP polling (not WebSocket) for job requests from agents
- AI-powered GPU selection using XGBoost models
- Python subprocess execution for actual workloads

## Development Workflow

### Local Development
1. Start infrastructure: `docker compose up -d`
2. Start ngrok tunnels: `ngrok start --all`
3. Update tunnel URLs: `./update_ngrok_urls.sh`
4. Start services: `./start_services.sh` or individual app commands

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

## Common Issues

1. **ngrok URL changes**: Run `./update_ngrok_urls.sh && git push`, then restart agents
2. **Database schema mismatches**: TimescaleDB schema has fewer fields than telemetry data
3. **Port conflicts**: Use `lsof -ti:PORT | xargs kill -9` to clear ports
4. **Agent connection failures**: Verify ngrok tunnels and URL synchronization