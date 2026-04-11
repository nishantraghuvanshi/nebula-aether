//! Agent library target.
//!
//! The `agent` crate is primarily a binary (`src/main.rs`) that runs on remote
//! GPU hosts, polls NVML, and publishes telemetry to NATS. This library target
//! exposes the hot-path types and helpers so they can be exercised by criterion
//! benchmarks (`benches/`) and integration tests (`tests/`) without pulling in
//! the full binary.

pub mod hotpath;
