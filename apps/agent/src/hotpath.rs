//! Telemetry hot-path types and helpers.
//!
//! Everything in this module is on the per-tick critical path of the agent
//! (NVML read → `GpuTelemetry` build → JSON encode → NATS publish) or on the
//! job-completion path (stdout → `PerformanceMetrics`). It is factored out of
//! `main.rs` so that criterion benchmarks and integration tests can link
//! against it via the crate's library target.
//!
//! Runtime behavior is intended to be identical to the inline code that
//! previously lived in `main.rs`. The wire format of `GpuTelemetry` is
//! pinned by `tests/golden_json.rs`.

use serde::Serialize;

/// A single GPU telemetry sample. This struct's JSON encoding is the NATS
/// wire format on the `aether.telemetry.*` subject — do NOT reorder or rename
/// fields without coordinating with the Go orchestrator's decoder.
#[derive(Serialize, Debug, Clone)]
pub struct GpuTelemetry {
    // Identification
    pub gpu_id: String,
    pub gpu_name: String,

    // Performance & Utilization
    pub utilization_gpu: u32,
    pub utilization_memory_controller: u32,
    pub performance_state: String,
    pub clock_gpu_mhz: u32,
    pub clock_mem_mhz: u32,

    // Memory
    pub memory_used_mb: u64,
    pub memory_total_mb: u64,

    // Power & Thermal
    pub temperature_c: u32,
    pub power_draw_w: u32,
    pub throttling_reasons: String,
}

/// Raw per-tick inputs for `build_gpu_telemetry`. Keeps the field arithmetic
/// (`bytes / 1024 / 1024`) and the `gpu_id` format in one place so benches
/// hit the exact code the production agent runs. `hostname` is a separate
/// argument to `build_gpu_telemetry` so the per-GPU loop can borrow it
/// without an extra allocation per tick.
pub struct GpuSampleInputs {
    pub gpu_index: u32,
    pub gpu_name: String,
    pub utilization_gpu: u32,
    pub utilization_memory: u32,
    pub performance_state: String,
    pub clock_gpu_mhz: u32,
    pub clock_mem_mhz: u32,
    pub memory_used_bytes: u64,
    pub memory_total_bytes: u64,
    pub temperature_c: u32,
    pub power_draw_w: u32,
    pub throttling_reasons: String,
}

/// Build a single `GpuTelemetry` sample from raw NVML-shaped inputs. This is
/// the exact code that runs on every tick of the per-GPU polling loop in
/// `main.rs`.
pub fn build_gpu_telemetry(hostname: &str, inputs: GpuSampleInputs) -> GpuTelemetry {
    let gpu_id = format!("{}:gpu-{}", hostname, inputs.gpu_index);
    GpuTelemetry {
        gpu_id,
        gpu_name: inputs.gpu_name,
        utilization_gpu: inputs.utilization_gpu,
        utilization_memory_controller: inputs.utilization_memory,
        performance_state: inputs.performance_state,
        clock_gpu_mhz: inputs.clock_gpu_mhz,
        clock_mem_mhz: inputs.clock_mem_mhz,
        memory_used_mb: inputs.memory_used_bytes / 1024 / 1024,
        memory_total_mb: inputs.memory_total_bytes / 1024 / 1024,
        temperature_c: inputs.temperature_c,
        power_draw_w: inputs.power_draw_w,
        throttling_reasons: inputs.throttling_reasons,
    }
}

/// Per-job performance metrics extracted from a subprocess's stdout.
#[derive(Serialize, Debug, Clone)]
pub struct PerformanceMetrics {
    // Core Performance Metrics
    pub throughput: Option<f64>,             // Job-specific throughput (samples/sec, fps, etc.)
    pub samples_per_second: Option<f64>,     // Processing rate
    pub completion_time_sec: Option<f64>,    // Time to complete workload
    pub accuracy: Option<f64>,               // Accuracy percentage for ML jobs

    // Resource Efficiency
    pub memory_efficiency: Option<f64>,      // Memory utilization efficiency (0-1)
    pub computational_efficiency: Option<f64>, // GPU compute efficiency (0-1)
    pub peak_memory_usage_mb: Option<u64>,   // Peak memory usage during job

    // Job-Specific Metrics
    pub frames_processed: Option<u64>,       // For video/rendering jobs
    pub batches_processed: Option<u64>,      // For ML training jobs
    pub iterations_completed: Option<u64>,   // For simulation jobs
    pub final_result: Option<String>,        // Final numerical result

    // Quality Metrics
    pub error_rate: Option<f64>,             // Error rate for applicable jobs
    pub convergence_achieved: Option<bool>,  // For optimization jobs
    pub quality_score: Option<f64>,          // Overall quality metric

    // Resource Usage Patterns
    pub avg_gpu_utilization: Option<f64>,    // Average GPU usage during job
    pub max_gpu_utilization: Option<f64>,    // Peak GPU usage
    pub thermal_events: Option<u32>,         // Number of thermal issues
}

impl PerformanceMetrics {
    pub fn new() -> Self {
        PerformanceMetrics {
            throughput: None,
            samples_per_second: None,
            completion_time_sec: None,
            accuracy: None,
            memory_efficiency: None,
            computational_efficiency: None,
            peak_memory_usage_mb: None,
            frames_processed: None,
            batches_processed: None,
            iterations_completed: None,
            final_result: None,
            error_rate: None,
            convergence_achieved: None,
            quality_score: None,
            avg_gpu_utilization: None,
            max_gpu_utilization: None,
            thermal_events: None,
        }
    }
}

impl Default for PerformanceMetrics {
    fn default() -> Self {
        Self::new()
    }
}

pub fn extract_performance_metrics(
    stdout: &[u8],
    job_type: &str,
    start_time: u64,
    end_time: u64,
) -> (PerformanceMetrics, String) {
    let output = String::from_utf8_lossy(stdout);
    let lines: Vec<&str> = output.lines().collect();
    let mut metrics = PerformanceMetrics::new();
    let mut summary_parts = Vec::new();

    // Calculate actual completion time
    metrics.completion_time_sec = Some((end_time - start_time) as f64);

    // Parse output based on job type
    match job_type {
        "training" => extract_training_metrics(&mut metrics, &lines, &mut summary_parts),
        "inference" => extract_inference_metrics(&mut metrics, &lines, &mut summary_parts),
        "compute" => extract_compute_metrics(&mut metrics, &lines, &mut summary_parts),
        "simulation" => extract_simulation_metrics(&mut metrics, &lines, &mut summary_parts),
        "rendering" => extract_rendering_metrics(&mut metrics, &lines, &mut summary_parts),
        "encoding" => extract_encoding_metrics(&mut metrics, &lines, &mut summary_parts),
        "scientific" => extract_scientific_metrics(&mut metrics, &lines, &mut summary_parts),
        "llm" => extract_llm_metrics(&mut metrics, &lines, &mut summary_parts),
        "memory" => extract_memory_metrics(&mut metrics, &lines, &mut summary_parts),
        _ => extract_generic_metrics(&mut metrics, &lines, &mut summary_parts),
    }

    // Extract common metrics across all job types
    extract_common_metrics(&mut metrics, &lines, &mut summary_parts);

    let summary = if summary_parts.is_empty() {
        if output.is_empty() {
            "No output captured".to_string()
        } else {
            format!(
                "Completed in {:.2}s with {} lines of output",
                metrics.completion_time_sec.unwrap_or(0.0),
                lines.len()
            )
        }
    } else {
        summary_parts.join(" | ")
    };

    (metrics, summary)
}

fn extract_training_metrics(metrics: &mut PerformanceMetrics, lines: &[&str], summary: &mut Vec<String>) {
    for line in lines.iter().rev().take(30) {
        let line = line.trim();

        // Training-specific patterns
        if line.contains("samples/sec") || line.contains("Steps/second") {
            if let Some(rate) = extract_number_from_pattern(line, &["samples/sec", "Steps/second"]) {
                metrics.samples_per_second = Some(rate);
                summary.push(format!("Rate:{:.1} samples/sec", rate));
            }
        }

        if line.contains("Accuracy:") || line.contains("accuracy:") {
            if let Some(acc) = extract_percentage_from_line(line) {
                metrics.accuracy = Some(acc);
                summary.push(format!("Acc:{:.2}%", acc));
            }
        }

        if line.contains("Epoch") && line.contains("completed") {
            if let Some(epochs) = extract_number_from_pattern(line, &["Epoch"]) {
                metrics.iterations_completed = Some(epochs as u64);
            }
        }

        if line.contains("Loss:") {
            if let Some(loss) = extract_number_from_pattern(line, &["Loss:"]) {
                metrics.final_result = Some(format!("Loss: {:.4}", loss));
            }
        }
    }
}

fn extract_inference_metrics(metrics: &mut PerformanceMetrics, lines: &[&str], summary: &mut Vec<String>) {
    for line in lines.iter().rev().take(30) {
        let line = line.trim();

        if line.contains("samples/sec") || line.contains("Throughput:") {
            if let Some(rate) = extract_number_from_pattern(line, &["samples/sec", "Throughput:"]) {
                metrics.throughput = Some(rate);
                summary.push(format!("Throughput:{:.1}/sec", rate));
            }
        }

        if line.contains("confidence:") || line.contains("Average confidence:") {
            if let Some(conf) = extract_number_from_pattern(line, &["confidence:"]) {
                metrics.accuracy = Some(conf * 100.0);
                summary.push(format!("Conf:{:.3}", conf));
            }
        }

        if line.contains("Processing batch") {
            if let Some(batches) = extract_number_from_pattern(line, &["batch"]) {
                metrics.batches_processed = Some(batches as u64);
            }
        }
    }
}

fn extract_simulation_metrics(metrics: &mut PerformanceMetrics, lines: &[&str], summary: &mut Vec<String>) {
    for line in lines.iter().rev().take(30) {
        let line = line.trim();

        // Monte Carlo and simulation patterns
        if line.contains("samples/sec") || line.contains("Performance:") {
            if let Some(rate) = extract_number_from_pattern(line, &["samples/sec", "Performance:"]) {
                metrics.samples_per_second = Some(rate);
                summary.push(format!("Perf:{:.0} samples/sec", rate));
            }
        }

        if line.contains("π estimate:") || line.contains("estimate:") {
            if let Some(result) = extract_number_from_pattern(line, &["estimate:"]) {
                metrics.final_result = Some(format!("π ≈ {:.6}", result));
            }
        }

        if line.contains("Accuracy:") && line.contains("%") {
            if let Some(acc) = extract_percentage_from_line(line) {
                metrics.accuracy = Some(acc);
                summary.push(format!("Accuracy:{:.2}%", acc));
            }
        }

        if line.contains("Rounds completed:") {
            if let Some(rounds) = extract_number_from_pattern(line, &["Rounds completed:"]) {
                metrics.iterations_completed = Some(rounds as u64);
            }
        }

        if line.contains("TFLOPS") {
            if let Some(flops) = extract_number_from_pattern(line, &["TFLOPS"]) {
                metrics.computational_efficiency = Some(flops / 10.0); // Normalize to 0-1 scale
                summary.push(format!("Compute:{:.2} TFLOPS", flops));
            }
        }
    }
}

fn extract_compute_metrics(metrics: &mut PerformanceMetrics, lines: &[&str], summary: &mut Vec<String>) {
    for line in lines.iter().rev().take(30) {
        let line = line.trim();

        if line.contains("GFLOPS") || line.contains("TFLOPS") {
            if let Some(flops) = extract_number_from_pattern(line, &["GFLOPS", "TFLOPS"]) {
                metrics.throughput = Some(flops);
                summary.push(format!("FLOPS:{:.2}", flops));
            }
        }

        if line.contains("Iteration") && line.contains("completed") {
            if let Some(iter) = extract_number_from_pattern(line, &["Iteration"]) {
                metrics.iterations_completed = Some(iter as u64);
            }
        }
    }
}

fn extract_rendering_metrics(metrics: &mut PerformanceMetrics, lines: &[&str], summary: &mut Vec<String>) {
    for line in lines.iter().rev().take(30) {
        let line = line.trim();

        if line.contains("FPS") || line.contains("frames/sec") {
            if let Some(fps) = extract_number_from_pattern(line, &["FPS", "frames/sec"]) {
                metrics.throughput = Some(fps);
                summary.push(format!("FPS:{:.1}", fps));
            }
        }

        if line.contains("frames") && line.contains("processed") {
            if let Some(frames) = extract_number_from_pattern(line, &["frames"]) {
                metrics.frames_processed = Some(frames as u64);
            }
        }

        if line.contains("samples") && line.contains("per pixel") {
            if let Some(quality) = extract_number_from_pattern(line, &["samples"]) {
                metrics.quality_score = Some(quality / 100.0);
            }
        }
    }
}

fn extract_encoding_metrics(metrics: &mut PerformanceMetrics, lines: &[&str], summary: &mut Vec<String>) {
    for line in lines.iter().rev().take(30) {
        let line = line.trim();

        if line.contains("frames") && (line.contains("encoded") || line.contains("processed")) {
            if let Some(frames) = extract_number_from_pattern(line, &["frames"]) {
                metrics.frames_processed = Some(frames as u64);
            }
        }

        if line.contains("fps") || line.contains("FPS") {
            if let Some(fps) = extract_number_from_pattern(line, &["fps", "FPS"]) {
                metrics.throughput = Some(fps);
                summary.push(format!("Encoding:{:.1} fps", fps));
            }
        }
    }
}

fn extract_scientific_metrics(metrics: &mut PerformanceMetrics, lines: &[&str], summary: &mut Vec<String>) {
    for line in lines.iter().rev().take(30) {
        let line = line.trim();

        if line.contains("residues") || line.contains("steps") {
            if let Some(steps) = extract_number_from_pattern(line, &["residues", "steps"]) {
                metrics.iterations_completed = Some(steps as u64);
            }
        }

        if line.contains("ns/day") || line.contains("timesteps/sec") {
            if let Some(rate) = extract_number_from_pattern(line, &["ns/day", "timesteps/sec"]) {
                metrics.throughput = Some(rate);
                summary.push(format!("Rate:{:.1}", rate));
            }
        }
    }
}

fn extract_llm_metrics(metrics: &mut PerformanceMetrics, lines: &[&str], summary: &mut Vec<String>) {
    for line in lines.iter().rev().take(30) {
        let line = line.trim();

        if line.contains("tokens/sec") || line.contains("tokens per second") {
            if let Some(rate) = extract_number_from_pattern(line, &["tokens/sec", "tokens per second"]) {
                metrics.throughput = Some(rate);
                summary.push(format!("Tokens:{:.1}/sec", rate));
            }
        }

        if line.contains("training steps") || line.contains("steps") {
            if let Some(steps) = extract_number_from_pattern(line, &["steps"]) {
                metrics.iterations_completed = Some(steps as u64);
            }
        }

        if line.contains("perplexity") {
            if let Some(perp) = extract_number_from_pattern(line, &["perplexity"]) {
                metrics.quality_score = Some(1.0 / perp.max(1.0)); // Lower perplexity = better quality
            }
        }
    }
}

fn extract_memory_metrics(metrics: &mut PerformanceMetrics, lines: &[&str], summary: &mut Vec<String>) {
    for line in lines.iter().rev().take(30) {
        let line = line.trim();

        if line.contains("GB/s") || line.contains("bandwidth") {
            if let Some(bw) = extract_number_from_pattern(line, &["GB/s", "bandwidth"]) {
                metrics.throughput = Some(bw);
                summary.push(format!("BW:{:.1} GB/s", bw));
            }
        }

        if line.contains("allocation") && line.contains("successful") {
            metrics.memory_efficiency = Some(1.0);
            summary.push("Memory allocation: SUCCESS".to_string());
        }
    }
}

fn extract_generic_metrics(metrics: &mut PerformanceMetrics, lines: &[&str], summary: &mut Vec<String>) {
    for line in lines.iter().rev().take(30) {
        let line = line.trim();

        // Generic performance indicators
        if line.contains("completed successfully") {
            summary.push("SUCCESS".to_string());
        }

        if line.contains("performance:") || line.contains("Performance:") {
            if let Some(perf) = extract_number_from_pattern(line, &["performance:", "Performance:"]) {
                metrics.throughput = Some(perf);
            }
        }
    }
}

fn extract_common_metrics(metrics: &mut PerformanceMetrics, lines: &[&str], summary: &mut Vec<String>) {
    for line in lines.iter().rev().take(50) {
        let line = line.trim();

        // Memory usage patterns
        if line.contains("Peak GPU memory:") || line.contains("memory:") && line.contains("MB") {
            if let Some(mem) = extract_number_from_pattern(line, &["memory:", "Peak GPU memory:"]) {
                metrics.peak_memory_usage_mb = Some(mem as u64);
                summary.push(format!("Mem:{:.0}MB", mem));
            }
        }

        // Error patterns
        if line.contains("error") || line.contains("failed") || line.contains("Error") {
            metrics.error_rate = Some(1.0);
        }

        // Success patterns
        if line.contains("completed successfully") || line.contains("SUCCESS") {
            summary.push("✅ COMPLETED".to_string());
        }
    }
}

// Helper function to extract numbers from specific patterns
fn extract_number_from_pattern(line: &str, patterns: &[&str]) -> Option<f64> {
    for pattern in patterns {
        if let Some(pos) = line.find(pattern) {
            let after_pattern = &line[pos + pattern.len()..];
            // Look for the first number after the pattern
            let number_str: String = after_pattern
                .chars()
                .skip_while(|c| !c.is_numeric() && *c != '.')
                .take_while(|c| c.is_numeric() || *c == '.' || *c == ',' || *c == '_')
                .collect();

            if let Ok(num) = number_str.replace(',', "").replace('_', "").parse::<f64>() {
                return Some(num);
            }
        }
    }
    None
}

// Helper function to extract percentage values
fn extract_percentage_from_line(line: &str) -> Option<f64> {
    // Look for patterns like "95.2%" or "accuracy: 95.2"
    let cleaned = line.replace('%', "");
    if let Some(num) = extract_number_from_pattern(&cleaned, &["accuracy:", "Accuracy:", ":"]) {
        return Some(num);
    }
    None
}
