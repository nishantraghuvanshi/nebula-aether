# Aether Project Progress Log

This log records the steps taken, commands run, and how to verify the system at each stage.

## Phase 1: Foundation

### 2025-09-02 — Monorepo Initialization and Infra Services

- Initialized Turborepo (Next.js starter) and scaffolded monorepo
  - Command:
    - npx create-turbo@latest aether
- Cleaned scaffold
  - Commands:
    - rm -rf apps/docs
    - mv apps/web apps/dashboard
    - rm -rf packages/eslint-config packages/typescript-config
- Verified/retained root configuration
  - Files:
    - turbo.json (default tasks retained)
    - .gitignore (includes node_modules, build outputs, env files)
- Added Docker Compose for NATS (JetStream) and TimescaleDB
  - File: docker-compose.yml
  - Services:
    - nats:2.9 with -js
    - timescale/timescaledb:latest-pg14 with user/db aether
- Started services
  - Commands:
    - docker compose -f docker-compose.yml up

### Current Repo Structure (relevant excerpts)

- apps/dashboard — Next.js app (default starter)
- docker-compose.yml — NATS + TimescaleDB
- .gitignore — Node/Yarn/Turbo/Vercel/build/env ignores
- turbo.json — build/lint/dev tasks

## How to Run/Verify

### 1) Start backing services

- Foreground logs:
  - docker compose up
- Detached:
  - docker compose up -d

Expected:
- NATS ready on ports 4222 (client) and 8222 (HTTP mgmt)
- TimescaleDB (PostgreSQL 14) ready on 5432

Check status:
- docker compose ps

### 2) Quick NATS checks

- HTTP monitoring (should return JSON):
  - curl http://localhost:8222/varz | head
- Use a NATS CLI if installed (optional):
  - nats --server nats://127.0.0.1:4222 ping

### 3) Quick TimescaleDB/Postgres checks

- If you have psql locally:
  - PGPASSWORD=aether psql -h 127.0.0.1 -U aether -d aether -c "SELECT version();"
- Create a test table (optional):
  - PGPASSWORD=aether psql -h 127.0.0.1 -U aether -d aether -c "CREATE TABLE IF NOT EXISTS test(id int primary key, ts timestamptz default now());"

### 4) Run the dashboard app (Next.js)

- Install deps and start dev (from repo root or apps/dashboard):
  - npm install
  - npm run dev (starts all apps)
  - Or just dashboard:
    - cd apps/dashboard && npm install && npm run dev
- Visit: http://localhost:3000

## Notes

- Docker compose warns that `version` is obsolete; safe to remove later.
- The compose file creates a named volume aether_db_data for Timescale persistence.

## Next Up

- Add Rust telemetry agent (apps/agent) that streams metrics to NATS.
- Add Go orchestrator and Python AI Core in subsequent phases.

### 2025-09-02 — NATS Monitoring Enabled and DB Verified

- Enabled NATS HTTP monitoring on port 8222
  - File updated: docker-compose.yml (`command: "-js -m 8222"`)
  - Commands:
    - docker compose up -d
    - docker compose ps
- Verified NATS monitoring endpoint
  - Command:
    - curl -s http://localhost:8222/varz | head -n 5
- Verified TimescaleDB from inside container (local psql not installed)
  - Command:
    - docker exec -i aether-timescaledb-1 psql -U aether -d aether -c "SELECT version();"

### 2025-09-02 — Telemetry Agent (Rust) Scaffolded

- Created agent project under apps/agent
  - Commands:
    - mkdir -p apps/agent
    - cd apps/agent && cargo init --bin --vcs=none
- Added dependencies (tokio, nvml-wrapper). Deferred nats until we publish telemetry.
  - File: apps/agent/Cargo.toml
- Implemented initial GPU probe
  - macOS guard message (NVML unsupported on macOS)
  - Linux path uses NVML to print GPU name
- Built and ran agent
  - Command: cargo run
  - Output (on macOS):
    - "Starting Aether Telemetry Agent..."
    - "NVML is not supported on macOS. Run this agent on a Linux machine with NVIDIA drivers."

