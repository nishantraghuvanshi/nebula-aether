//! Criterion benchmarks for the Rust telemetry agent's per-tick hot path.
//!
//! Three groups map to the three main costs on every NVML sampling tick:
//!
//! 1. `bench_sample_build` — constructing the `GpuTelemetry` struct from the
//!    NVML-shaped inputs (format! calls, `bytes / 1024 / 1024` arithmetic).
//! 2. `bench_serialize` — `serde_json::to_vec` on a populated `GpuTelemetry`.
//!    This is the largest single heap allocation per tick today, and the
//!    first target of the follow-up perf work (buffer reuse / `to_writer`).
//! 3. `bench_extract_perf_metrics` — parses canned subprocess stdout for each
//!    of the 10 job-type-specific extractors.
//!
//! These benchmarks run against the `agent` library target (`src/lib.rs` →
//! `src/hotpath.rs`), so they exercise the exact code the production binary
//! runs. To run locally:
//!
//! ```sh
//! cargo bench -p agent --bench telemetry_hotpath
//! ```
//!
//! HTML reports land in `target/criterion/report/index.html`.

use criterion::{black_box, criterion_group, criterion_main, Criterion};

use agent::hotpath::{
    build_gpu_telemetry, extract_performance_metrics, GpuSampleInputs, GpuTelemetry,
};

/// Deterministic fixtures so bench numbers are repeatable across runs. These
/// values are representative of a mid-load A100-class GPU sample and do not
/// correspond to any real machine.
mod fixtures {
    use super::*;

    pub const HOSTNAME: &str = "runpod-host-abc123";
    pub const GPU_INDEX: u32 = 0;

    /// Build a fresh `GpuSampleInputs` with realistic values. Each call
    /// allocates new Strings so benches measure the allocation cost they
    /// would incur in the production loop, which also allocates fresh
    /// Strings every tick via NVML accessors.
    pub fn sample_inputs() -> GpuSampleInputs {
        GpuSampleInputs {
            gpu_index: GPU_INDEX,
            gpu_name: "NVIDIA A100-SXM4-40GB".to_string(),
            utilization_gpu: 72,
            utilization_memory: 55,
            performance_state: "P0".to_string(),
            clock_gpu_mhz: 1410,
            clock_mem_mhz: 1215,
            memory_used_bytes: 24_000_000_000,
            memory_total_bytes: 42_949_672_960, // 40 GiB
            temperature_c: 68,
            power_draw_w: 310,
            throttling_reasons: "GpuIdle".to_string(),
        }
    }

    /// A complete `GpuTelemetry` suitable for the serialization bench.
    pub fn sample_telemetry() -> GpuTelemetry {
        build_gpu_telemetry(HOSTNAME, sample_inputs())
    }

    // Canned subprocess stdout snippets used by `bench_extract_perf_metrics`.
    // These mirror the shape of output produced by the Python fallback
    // scripts in `main.rs::create_fallback_script`.
    pub const TRAINING_STDOUT: &[u8] = b"\
Epoch 1/5\n\
  Batch 1/10 - Loss: 0.8421\n\
  Batch 10/10 - Loss: 0.2314\n\
Epoch 1 completed in 4.21s\n\
Rate: 245.3 samples/sec\n\
Accuracy: 95.2%\n\
Training simulation completed successfully!\n\
";

    pub const INFERENCE_STDOUT: &[u8] = b"\
Processing batch 1/20\n\
  Average confidence: 0.871\n\
Processing batch 20/20\n\
  Average confidence: 0.892\n\
Inference completed in 4.12s\n\
Throughput: 155.3 samples/sec\n\
";

    pub const COMPUTE_STDOUT: &[u8] = b"\
Iteration 1 completed\n\
Iteration 5 completed\n\
Computation result: 1238471.28\n\
Performance: 847.12 GFLOPS\n\
Peak GPU memory: 18432 MB\n\
";

    pub const SIMULATION_STDOUT: &[u8] = b"\
Rounds completed: 1000\n\
pi estimate: 3.141829\n\
Accuracy: 99.91%\n\
Performance: 4.82 TFLOPS\n\
142153.7 samples/sec\n\
";
}

fn bench_sample_build(c: &mut Criterion) {
    c.bench_function("sample_build", |b| {
        b.iter(|| {
            let inputs = fixtures::sample_inputs();
            let telemetry = build_gpu_telemetry(black_box(fixtures::HOSTNAME), inputs);
            black_box(telemetry);
        });
    });
}

fn bench_serialize(c: &mut Criterion) {
    let telemetry = fixtures::sample_telemetry();
    c.bench_function("serialize_to_vec", |b| {
        b.iter(|| {
            let bytes = serde_json::to_vec(black_box(&telemetry)).unwrap();
            black_box(bytes);
        });
    });
}

fn bench_extract_perf_metrics(c: &mut Criterion) {
    let cases: &[(&str, &[u8])] = &[
        ("training", fixtures::TRAINING_STDOUT),
        ("inference", fixtures::INFERENCE_STDOUT),
        ("compute", fixtures::COMPUTE_STDOUT),
        ("simulation", fixtures::SIMULATION_STDOUT),
    ];

    let mut group = c.benchmark_group("extract_perf_metrics");
    for (job_type, stdout) in cases {
        group.bench_with_input(*job_type, stdout, |b, stdout| {
            b.iter(|| {
                let (metrics, summary) = extract_performance_metrics(
                    black_box(stdout),
                    black_box(job_type),
                    black_box(1_700_000_000),
                    black_box(1_700_000_042),
                );
                black_box((metrics, summary));
            });
        });
    }
    group.finish();
}

criterion_group!(
    benches,
    bench_sample_build,
    bench_serialize,
    bench_extract_perf_metrics
);
criterion_main!(benches);
