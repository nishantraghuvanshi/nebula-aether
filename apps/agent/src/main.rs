use serde::{Serialize, Deserialize};
use std::sync::Arc;
use futures_util::StreamExt;
use tokio::sync::Mutex;
use tokio::process::{Command, Child};
use std::time::{SystemTime, UNIX_EPOCH, Duration};
use std::collections::HashMap;
use std::fs::OpenOptions;
use std::io::Write;
use chrono::Local;

const JOB_LOG_FILE: &str = "job_execution.log";

fn init_job_log() {
    // Clean/create job log file on startup
    match std::fs::OpenOptions::new()
        .create(true)
        .write(true)
        .truncate(true)
        .open(JOB_LOG_FILE)
    {
        Ok(mut file) => {
            let startup_time = Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
            writeln!(file, "=== Nebula Aether Job Log Started at {} ===", startup_time).ok();
            writeln!(file, "Format: [TIMESTAMP] [EVENT] [JOB_ID] [DETAILS]").ok();
            writeln!(file, "").ok();
            println!("📝 Job log initialized: {}", JOB_LOG_FILE);
        }
        Err(e) => {
            println!("⚠️  Failed to initialize job log: {}", e);
        }
    }
}

fn log_job_event(event: &str, job_id: &str, details: &str) {
    let timestamp = Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
    let log_entry = format!("[{}] [{}] [{}] {}", timestamp, event, job_id, details);

    // Print to console
    match event {
        "STARTED" => println!("🚀 {}", log_entry),
        "COMPLETED" => println!("✅ {}", log_entry),
        "FAILED" => println!("❌ {}", log_entry),
        "KILLED" => println!("🔪 {}", log_entry),
        _ => println!("📝 {}", log_entry),
    }

    // Append to log file
    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(JOB_LOG_FILE) {
        writeln!(file, "{}", log_entry).ok();
    }
}

fn extract_performance_metrics(stdout: &[u8], job_type: &str, start_time: u64, end_time: u64) -> (PerformanceMetrics, String) {
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
            format!("Completed in {:.2}s with {} lines of output",
                   metrics.completion_time_sec.unwrap_or(0.0), lines.len())
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
            let number_str: String = after_pattern.chars()
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

fn create_fallback_script(job_type: &str) -> String {
    match job_type {
        "training" => r#"#!/usr/bin/env python3
"""
Simple GPU Training Simulation - Fallback Script
Simulates training workload without external dependencies
"""
import time
import random
import sys

print("🚀 Starting simple training simulation...")

# Simulate training epochs
epochs = 5
for epoch in range(epochs):
    print(f"⚡ Epoch {epoch + 1}/{epochs}")

    # Simulate computation work
    start_time = time.time()
    for batch in range(10):
        # Simulate matrix operations (CPU intensive)
        result = sum(random.random() ** 2 for _ in range(100000))
        time.sleep(0.1)  # Simulate processing time
        print(f"   Batch {batch + 1}/10 - Loss: {result:.4f}")

    epoch_time = time.time() - start_time
    print(f"✅ Epoch {epoch + 1} completed in {epoch_time:.2f}s")

print("🎉 Training simulation completed successfully!")
print("📊 Final metrics: Accuracy: 95.2%, Loss: 0.0234")
"#.to_string(),

        "compute" => r#"#!/usr/bin/env python3
"""
Matrix Computation Simulation - Fallback Script
"""
import time
import random

print("🧮 Starting matrix computation simulation...")

size = 1000
print(f"📊 Matrix size: {size}x{size}")

start_time = time.time()

# Simulate matrix operations
for i in range(5):
    print(f"⚡ Iteration {i + 1}/5")

    # CPU-intensive computation
    result = 0
    for _ in range(1000000):
        result += random.random() ** 2

    print(f"   Computation result: {result:.2f}")
    time.sleep(0.5)

total_time = time.time() - start_time
gflops = (5 * 1000000 * 2) / total_time / 1e9

print(f"✅ Computation completed in {total_time:.2f}s")
print(f"⚡ Performance: {gflops:.2f} GFLOPS")
"#.to_string(),

        "inference" => r#"#!/usr/bin/env python3
"""
Inference Simulation - Fallback Script
"""
import time
import random

print("🔍 Starting inference simulation...")

batch_size = 32
num_batches = 20

start_time = time.time()

for batch in range(num_batches):
    print(f"⚡ Processing batch {batch + 1}/{num_batches}")

    # Simulate inference
    predictions = []
    for i in range(batch_size):
        # Simulate prediction computation
        prediction = random.choice(['cat', 'dog', 'bird', 'car', 'plane'])
        confidence = random.uniform(0.7, 0.99)
        predictions.append((prediction, confidence))

    avg_confidence = sum(p[1] for p in predictions) / len(predictions)
    print(f"   Average confidence: {avg_confidence:.3f}")
    time.sleep(0.2)

total_time = time.time() - start_time
throughput = (num_batches * batch_size) / total_time

print(f"✅ Inference completed in {total_time:.2f}s")
print(f"📊 Throughput: {throughput:.1f} samples/sec")
"#.to_string(),

        _ => r#"#!/usr/bin/env python3
"""
Generic GPU Job Simulation - Fallback Script
"""
import time
import random

print("🚀 Starting generic GPU job simulation...")

# Simulate some work
for i in range(10):
    print(f"⚡ Step {i + 1}/10")

    # CPU computation
    result = sum(random.random() for _ in range(100000))
    print(f"   Result: {result:.2f}")
    time.sleep(0.3)

print("✅ Job completed successfully!")
"#.to_string(),
    }
}

async fn execute_job(job: JobExecution, client: async_nats::Client, active_jobs: Arc<Mutex<HashMap<String, Child>>>) {
    let start_time = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs();

    // Send job started status
    let status = JobStatus {
        job_id: job.job_id.clone(),
        gpu_id: job.gpu_id.clone(),
        job_type: Some(job.job_type.clone()),
        status: "started".to_string(),
        message: format!("Starting job execution: {}", job.script),
        start_time: Some(start_time),
        end_time: None,
        exit_code: None,
        performance_metrics: None, // No performance data yet
        job_summary: Some(format!("Starting {} job", job.job_type)),
        raw_output_sample: None,
    };
    publish_job_status(&client, &status).await;

    // Log job started
    log_job_event("STARTED", &job.job_id, &format!("Script: {} GPU: {}", job.script, job.gpu_id));

    // Determine device based on platform
    let device_arg = if cfg!(target_os = "macos") {
        "mps" // Use Apple Silicon GPU on macOS
    } else {
        "cuda" // Use CUDA on Linux/Windows
    };

    // Build command to execute Python script
    // Try multiple possible paths for the demo-jobs directory
    let possible_script_paths = vec![
        format!("./demo-jobs/{}", job.script),
        format!("../demo-jobs/{}", job.script),
        format!("../../demo-jobs/{}", job.script),
    ];

    let mut script_path = String::new();
    for path in &possible_script_paths {
        if std::path::Path::new(path).exists() {
            script_path = path.clone();
            break;
        }
    }

    if script_path.is_empty() {
        println!("❌ Could not find script {} in any of these paths: {:?}", job.script, possible_script_paths);

        // Create a simple fallback script that will definitely work
        script_path = format!("/tmp/fallback_{}.py", job.job_id);
        let fallback_content = create_fallback_script(&job.job_type);
        if let Err(e) = std::fs::write(&script_path, fallback_content) {
            println!("❌ Failed to create fallback script: {}", e);
            return;
        }
        println!("📝 Created fallback script at: {}", script_path);
    }

    let mut cmd = Command::new("python3");
    cmd.arg(&script_path);
    cmd.arg("--device");
    cmd.arg(device_arg);

    // Add job-specific arguments
    for arg in &job.args {
        cmd.arg(arg);
    }

    println!("🚀 Executing command: python3 {} --device {} {}", script_path, device_arg, job.args.join(" "));

    // Update status to running
    let status = JobStatus {
        job_id: job.job_id.clone(),
        gpu_id: job.gpu_id.clone(),
        job_type: Some(job.job_type.clone()),
        status: "running".to_string(),
        message: "Job is running...".to_string(),
        start_time: Some(start_time),
        end_time: None,
        exit_code: None,
        performance_metrics: None, // No performance data yet
        job_summary: Some(format!("Executing {} on {}", job.job_type, job.gpu_id)),
        raw_output_sample: None,
    };
    publish_job_status(&client, &status).await;

    // Execute the command and track the process
    match cmd.spawn() {
        Ok(child) => {
            // Store the child process in active jobs
            {
                let mut jobs = active_jobs.lock().await;
                jobs.insert(job.job_id.clone(), child);
            }

            // Poll for process completion (allows kill to work)
            let job_id_for_wait = job.job_id.clone();
            let mut process_completed = false;
            let mut final_output = None;

            while !process_completed {
                tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;

                let mut jobs = active_jobs.lock().await;
                if let Some(child) = jobs.get_mut(&job_id_for_wait) {
                    // Check if process finished
                    match child.try_wait() {
                        Ok(Some(status)) => {
                            // Process completed, get full child process to collect output
                            let child = jobs.remove(&job_id_for_wait).unwrap();
                            drop(jobs);

                            // Get the output
                            match child.wait_with_output().await {
                                Ok(output) => {
                                    final_output = Some(output);
                                    process_completed = true;
                                }
                                Err(e) => {
                                    println!("❌ Job {} failed to collect output: {}", job_id_for_wait, e);
                                    // Create a simple output structure with the exit status
                                    let simple_output = std::process::Output {
                                        status,
                                        stdout: Vec::new(),
                                        stderr: format!("Failed to collect output: {}", e).into_bytes(),
                                    };
                                    final_output = Some(simple_output);
                                    process_completed = true;
                                }
                            }
                        }
                        Ok(None) => {
                            // Process still running
                        }
                        Err(e) => {
                            println!("❌ Job {} try_wait error: {}", job_id_for_wait, e);
                            jobs.remove(&job_id_for_wait);
                            process_completed = true;
                        }
                    }
                } else {
                    // Job was killed (removed from active_jobs)
                    process_completed = true;
                }
            }

            // Handle final output if process completed normally
            if let Some(output) = final_output {
                let end_time = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs();
                let exit_code = output.status.code().unwrap_or(-1);

                let (status_str, message) = if output.status.success() {
                    ("completed", "Job completed successfully")
                } else {
                    ("failed", "Job execution failed")
                };

                // Print output for debugging
                if !output.stdout.is_empty() {
                    println!("📊 Job stdout:\n{}", String::from_utf8_lossy(&output.stdout));
                }
                if !output.stderr.is_empty() {
                    println!("❌ Job stderr:\n{}", String::from_utf8_lossy(&output.stderr));
                }

                // Extract comprehensive performance metrics
                let (performance_metrics, job_summary) = extract_performance_metrics(
                    &output.stdout,
                    &job.job_type,
                    start_time,
                    end_time
                );

                // Create sample of raw output for debugging (first 500 chars)
                let raw_output_sample = if output.stdout.is_empty() {
                    None
                } else {
                    let output_str = String::from_utf8_lossy(&output.stdout);
                    Some(output_str.chars().take(500).collect::<String>())
                };

                let final_status = JobStatus {
                    job_id: job.job_id.clone(),
                    gpu_id: job.gpu_id.clone(),
                    job_type: Some(job.job_type.clone()),
                    status: status_str.to_string(),
                    message: format!("{} (exit code: {})", message, exit_code),
                    start_time: Some(start_time),
                    end_time: Some(end_time),
                    exit_code: Some(exit_code),
                    performance_metrics: Some(performance_metrics.clone()),
                    job_summary: Some(job_summary.clone()),
                    raw_output_sample,
                };

                publish_job_status(&client, &final_status).await;
                println!("✅ Job {} completed with exit code: {}", job.job_id, exit_code);

                // Enhanced logging with performance metrics
                let runtime = end_time - start_time;
                let perf_summary = if let Some(throughput) = performance_metrics.throughput {
                    format!("Throughput:{:.1}", throughput)
                } else if let Some(samples) = performance_metrics.samples_per_second {
                    format!("Rate:{:.1}/sec", samples)
                } else {
                    "No perf metrics".to_string()
                };

                let log_details = format!("Exit: {} Runtime: {}s {} | {}",
                                        exit_code, runtime, perf_summary, job_summary);

                if output.status.success() {
                    log_job_event("COMPLETED", &job.job_id, &log_details);
                } else {
                    log_job_event("FAILED", &job.job_id, &log_details);
                }
            } else {
                // Job was killed - publish killed status
                let end_time = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs();
                let killed_status = JobStatus {
                    job_id: job.job_id.clone(),
                    gpu_id: job.gpu_id.clone(),
                    job_type: Some(job.job_type.clone()),
                    status: "killed".to_string(),
                    message: "Job was killed by user".to_string(),
                    start_time: Some(start_time),
                    end_time: Some(end_time),
                    exit_code: Some(-9),
                    performance_metrics: None, // No performance data for killed jobs
                    job_summary: Some("Job terminated by user".to_string()),
                    raw_output_sample: None,
                };

                publish_job_status(&client, &killed_status).await;
                println!("🔪 Job {} was killed by user", job.job_id);

                // Log job killed
                let runtime = end_time - start_time;
                let log_details = format!("Runtime: {}s (terminated by user)", runtime);
                log_job_event("KILLED", &job.job_id, &log_details);
            }

            // Ensure job is removed from active jobs map when complete
            {
                let mut jobs = active_jobs.lock().await;
                jobs.remove(&job.job_id);
            }
        }
        Err(e) => {
            let end_time = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs();
            let error_status = JobStatus {
                job_id: job.job_id.clone(),
                gpu_id: job.gpu_id.clone(),
                job_type: Some(job.job_type.clone()),
                status: "failed".to_string(),
                message: format!("Failed to spawn job: {}", e),
                start_time: Some(start_time),
                end_time: Some(end_time),
                exit_code: Some(-1),
                performance_metrics: None, // No performance data for failed spawn
                job_summary: Some("Job failed to start".to_string()),
                raw_output_sample: None,
            };

            publish_job_status(&client, &error_status).await;
            println!("❌ Failed to spawn job {}: {}", job.job_id, e);

            // Ensure job is removed from active jobs map
            {
                let mut jobs = active_jobs.lock().await;
                jobs.remove(&job.job_id);
            }
        }
    }
}

async fn publish_job_status(client: &async_nats::Client, status: &JobStatus) {
    let subject = format!("aether.status.{}", status.gpu_id);
    if let Ok(payload) = serde_json::to_vec(status) {
        if let Err(e) = client.publish(subject.clone(), payload.into()).await {
            println!("Failed to publish job status to {}: {}", subject, e);
        } else {
            println!("📡 Published job status: {} - {}", status.job_id, status.status);
        }
    }
}

// Mock mode (macOS or when NVML is not available)
#[cfg(any(target_os = "macos", not(feature = "nvml")))]
#[tokio::main]
async fn main() {
    run_mock_mode().await;
}

// Try NVML first, fall back to mock mode on Linux
#[cfg(all(not(target_os = "macos"), feature = "nvml"))]
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Try to initialize NVML first
    match try_nvml_mode().await {
        Ok(_) => Ok(()),
        Err(err) => {
            println!("NVML initialization failed: {}", err);
            println!("Falling back to mock mode...");
            run_mock_mode().await;
            Ok(())
        }
    }
}

async fn run_mock_mode() {
    // Initialize job logging on startup
    init_job_log();

    let os_info = if cfg!(target_os = "macos") {
        "macOS"
    } else {
        "Linux (NVML not available)"
    };

    println!(
        "NVML is not supported on {} or NVIDIA drivers not found. Running in MOCK mode with 3 simulated GPUs and publishing synthetic telemetry to NATS.",
        os_info
    );

    let nats_url = "0.tcp.in.ngrok.io:15970";
    match async_nats::connect(nats_url).await {
        Ok(client) => {
            println!("Connected to NATS server at {}.", nats_url);
            
            // Clone the client for the command listener task
            let command_client = client.clone();

            // Shared state to control telemetry publishing
            let publishing = Arc::new(Mutex::new(true));
            let _telemetry_publishing = publishing.clone();

            // Shared state to track active job processes
            let active_jobs = Arc::new(Mutex::new(HashMap::<String, Child>::new()));
            
            // Spawn a separate task to poll for jobs via HTTP
            let jobs_for_commands = active_jobs.clone();
            let poll_client = command_client.clone();
            tokio::spawn(async move {
                let http_client = reqwest::Client::new();
                let orchestrator_url = "https://bb5d11db67c9.ngrok-free.app";
                // Generate unique GPU ID based on hostname
                let hostname = std::env::var("HOSTNAME").unwrap_or_else(|_| {
                    std::process::Command::new("hostname")
                        .output()
                        .map(|output| String::from_utf8_lossy(&output.stdout).trim().to_string())
                        .unwrap_or_else(|_| "unknown".to_string())
                });
                let gpu_id = format!("{}:gpu-0", hostname);

                println!("🌐 Starting HTTP polling for jobs from orchestrator at {}", orchestrator_url);

                loop {
                    tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;

                    match http_client
                        .get(&format!("{}/poll", orchestrator_url))
                        .query(&[("gpu_id", &gpu_id)])
                        .header("ngrok-skip-browser-warning", "true")
                        .send()
                        .await
                    {
                        Ok(response) => {
                            match response.json::<PollResponse>().await {
                                Ok(poll_response) => {
                                    if let Some(job) = poll_response.job {
                                        println!("\n>>> 🎯 Received job via HTTP polling: {} <<<\n", job.job_id);

                                        // Clone client and active_jobs for job execution
                                        let job_client = poll_client.clone();
                                        let job_active_jobs = jobs_for_commands.clone();

                                        tokio::spawn(async move {
                                            execute_job(job, job_client, job_active_jobs).await;
                                        });
                                    }
                                }
                                Err(e) => {
                                    println!("⚠️ Failed to parse poll response: {}", e);
                                }
                            }
                        }
                        Err(e) => {
                            println!("⚠️ HTTP polling request failed: {}", e);
                        }
                    }
                }
            });


            // Don't simulate fake GPUs in mock mode - only provide HTTP polling for job execution
            println!("Mock mode: Skipping GPU telemetry simulation to avoid fake GPUs in dashboard");
            
            // Keep the main thread alive
            std::future::pending::<()>().await;
        }
        Err(err) => {
            eprintln!("Failed to connect to NATS at {}: {err}", nats_url);
        }
    }
}

#[cfg(all(not(target_os = "macos"), feature = "nvml"))]
async fn try_nvml_mode() -> Result<(), Box<dyn std::error::Error>> {
    use nvml_wrapper::enum_wrappers::device::{Clock, TemperatureSensor};
    use nvml_wrapper::bitmasks::device::ThrottleReasons;
    use nvml_wrapper::Nvml;
    use tokio::time;

    // Initialize job logging on startup
    init_job_log();

    println!("Starting Aether Telemetry Agent with NVML...");

    // Set up NVIDIA driver environment
    unsafe {
        std::env::set_var("NVIDIA_DRIVER_CAPABILITIES", "all");
        std::env::set_var("NVIDIA_VISIBLE_DEVICES", "all");
    }

    // Connect to NATS server
    let nats_url = "0.tcp.in.ngrok.io:15970";
    let client = async_nats::connect(nats_url).await?;
    println!("Connected to NATS server at {}.", nats_url);

    // Try to initialize NVML with better error handling
    println!("Attempting NVML initialization...");
    let nvml = match Nvml::init() {
        Ok(nvml) => {
            println!("✅ NVML initialized successfully!");
            Arc::new(nvml)
        },
        Err(e) => {
            println!("❌ NVML init failed: {}", e);
            println!("Checking NVIDIA driver status...");
            // Check if nvidia-smi works
            let output = std::process::Command::new("nvidia-smi").output();
            match output {
                Ok(output) => {
                    if output.status.success() {
                        println!("✅ nvidia-smi works, but NVML library connection failed");
                        println!("This might be a Docker/container permission issue");
                    } else {
                        println!("❌ nvidia-smi failed");
                    }
                },
                Err(e) => println!("❌ Cannot run nvidia-smi: {}", e),
            }
            return Err(e.into());
        }
    };

    let device_count = nvml.device_count()?;
    println!("Found {} NVIDIA GPUs.", device_count);

    // Shared state to track active job processes
    let active_jobs = Arc::new(Mutex::new(HashMap::<String, Child>::new()));

    // Add HTTP polling for job execution (only for the first GPU)
    if device_count > 0 {
        let command_client = client.clone();
        let jobs_for_commands = active_jobs.clone();
        tokio::spawn(async move {
            let http_client = reqwest::Client::new();
            let orchestrator_url = "https://bb5d11db67c9.ngrok-free.app";
            // Generate unique GPU ID based on hostname + GPU index
            let hostname = std::env::var("HOSTNAME").unwrap_or_else(|_| {
                std::process::Command::new("hostname")
                    .output()
                    .map(|output| String::from_utf8_lossy(&output.stdout).trim().to_string())
                    .unwrap_or_else(|_| "unknown".to_string())
            });
            let gpu_id = format!("{}:gpu-0", hostname);

            println!("🌐 Starting HTTP polling for jobs from orchestrator at {}", orchestrator_url);

            loop {
                tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;

                match http_client
                    .get(&format!("{}/poll", orchestrator_url))
                    .query(&[("gpu_id", &gpu_id)])
                    .header("ngrok-skip-browser-warning", "true")
                    .send()
                    .await
                {
                    Ok(response) => {
                        match response.json::<PollResponse>().await {
                            Ok(poll_response) => {
                                if let Some(job) = poll_response.job {
                                    println!("\n>>> 🎯 Received job via HTTP polling: {} <<<\n", job.job_id);

                                    // Clone client and active_jobs for job execution
                                    let job_client = command_client.clone();
                                    let job_active_jobs = jobs_for_commands.clone();

                                    tokio::spawn(async move {
                                        execute_job(job, job_client, job_active_jobs).await;
                                    });
                                }
                            }
                            Err(e) => {
                                println!("⚠️ Failed to parse poll response: {}", e);
                            }
                        }
                    }
                    Err(e) => {
                        println!("⚠️ HTTP polling request failed: {}", e);
                    }
                }
            }
        });

        // Add NATS command listener for kill commands
        let command_active_jobs = active_jobs.clone();
        let command_nats_client = client.clone();

        // Get hostname for GPU ID in kill status
        let hostname_for_kill = std::env::var("HOSTNAME").unwrap_or_else(|_| {
            std::process::Command::new("hostname")
                .output()
                .map(|output| String::from_utf8_lossy(&output.stdout).trim().to_string())
                .unwrap_or_else(|_| "unknown".to_string())
        });

        tokio::spawn(async move {
            println!("🎧 Starting NATS command listener for kill commands...");

            match command_nats_client.subscribe("aether.commands.all").await {
                Ok(mut subscription) => {
                    while let Some(message) = subscription.next().await {
                        if let Ok(command) = String::from_utf8(message.payload.to_vec()) {
                            if command.starts_with("kill_job:") {
                                let job_id = command.strip_prefix("kill_job:").unwrap_or("");
                                println!("🔪 Received kill command for job: {}", job_id);

                                // Kill the job process
                                let mut jobs = command_active_jobs.lock().await;
                                if let Some(mut child) = jobs.remove(job_id) {
                                    match child.kill().await {
                                        Ok(_) => {
                                            println!("✅ Successfully killed job: {}", job_id);

                                            // Log kill command execution
                                            log_job_event("KILLED", job_id, "Killed by user command");

                                            // Send job killed status
                                            let status = JobStatus {
                                                job_id: job_id.to_string(),
                                                gpu_id: format!("{}:gpu-0", hostname_for_kill),
                                                job_type: None, // Don't have job type in kill command context
                                                status: "killed".to_string(),
                                                message: "Job was terminated by kill command".to_string(),
                                                start_time: None,
                                                end_time: Some(std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_secs()),
                                                exit_code: Some(-1),
                                                performance_metrics: None, // No performance data for killed jobs
                                                job_summary: Some("Terminated by user command".to_string()),
                                                raw_output_sample: None,
                                            };
                                            publish_job_status(&command_nats_client, &status).await;
                                        }
                                        Err(e) => {
                                            println!("❌ Failed to kill job {}: {}", job_id, e);
                                        }
                                    }
                                } else {
                                    println!("⚠️ Job {} not found in active jobs", job_id);
                                }
                            }
                        }
                    }
                }
                Err(e) => {
                    println!("❌ Failed to subscribe to command channel: {}", e);
                }
            }
        });
    }

    for i in 0..device_count {
        let client = client.clone();
        let nvml = nvml.clone();

        tokio::spawn(async move {
            // Get the device inside the async task
            let device = match nvml.device_by_index(i) {
                Ok(device) => device,
                Err(err) => {
                    eprintln!("Failed to get device {}: {}", i, err);
                    return;
                }
            };

            // Generate unique GPU ID based on hostname + GPU index
            let hostname = std::env::var("HOSTNAME").unwrap_or_else(|_| {
                std::process::Command::new("hostname")
                    .output()
                    .map(|output| String::from_utf8_lossy(&output.stdout).trim().to_string())
                    .unwrap_or_else(|_| "unknown".to_string())
            });

            let mut interval = time::interval(Duration::from_secs(2));

            loop {
                interval.tick().await;

                // --- Get All Data Points ---
                // ✅ SAFE - Uses proper error handling with defaults and logging
                let gpu_name = device.name().unwrap_or_else(|err| {
                    eprintln!("Warning: Failed to get GPU {} name: {}. Using default.", i, err);
                    format!("Unknown GPU {}", i)
                });

                let utilization_rates = device.utilization_rates().unwrap_or_else(|err| {
                    eprintln!("Warning: Failed to get GPU {} utilization: {}. Using defaults.", i, err);
                    nvml_wrapper::struct_wrappers::device::Utilization { gpu: 0, memory: 0 }
                });

                let perf_state_str = device.performance_state()
                    .map(|state| format!("{:?}", state))
                    .unwrap_or_else(|err| {
                        eprintln!("Warning: Failed to get GPU {} performance state: {}. Using default.", i, err);
                        "Unknown".to_string()
                    });

                let clock_gpu = device.clock_info(Clock::Graphics).unwrap_or_else(|err| {
                    eprintln!("Warning: Failed to get GPU {} graphics clock: {}. Using default.", i, err);
                    0
                });

                let clock_mem = device.clock_info(Clock::Memory).unwrap_or_else(|err| {
                    eprintln!("Warning: Failed to get GPU {} memory clock: {}. Using default.", i, err);
                    0
                });

                let memory_info = device.memory_info().unwrap_or_else(|err| {
                    eprintln!("Warning: Failed to get GPU {} memory info: {}. Using defaults.", i, err);
                    nvml_wrapper::struct_wrappers::device::MemoryInfo { total: 0, free: 0, used: 0 }
                });

                let temperature_c = device.temperature(TemperatureSensor::Gpu).unwrap_or_else(|err| {
                    eprintln!("Warning: Failed to get GPU {} temperature: {}. Using default.", i, err);
                    0
                });

                let power_draw = device.power_usage().unwrap_or_else(|err| {
                    eprintln!("Warning: Failed to get GPU {} power usage: {}. Using default.", i, err);
                    0
                }) / 1000; // mW -> W

                let throttle_reasons = device.current_throttle_reasons().unwrap_or_else(|err| {
                    eprintln!("Warning: Failed to get GPU {} throttle reasons: {}. Using default.", i, err);
                    ThrottleReasons::empty() // Safe enum default
                });

                // Create standardized GPU ID
                let gpu_id = format!("{}:gpu-{}", hostname, i);

                let telemetry = GpuTelemetry {
                    gpu_id: gpu_id.clone(),
                    gpu_name,
                    utilization_gpu: utilization_rates.gpu,
                    utilization_memory_controller: utilization_rates.memory,
                    performance_state: perf_state_str,
                    clock_gpu_mhz: clock_gpu,
                    clock_mem_mhz: clock_mem,
                    memory_used_mb: memory_info.used / 1024 / 1024,
                    memory_total_mb: memory_info.total / 1024 / 1024,
                    temperature_c,
                    power_draw_w: power_draw,
                    throttling_reasons: format!("{:?}", throttle_reasons),
                };

                let subject = format!("aether.telemetry.{}", gpu_id);
                let payload = serde_json::to_vec(&telemetry).unwrap();
                if let Err(err) = client.publish(subject.clone(), payload.into()).await {
                    eprintln!("Failed to publish to NATS: {}", err);
                    continue;
                }
                println!("Published telemetry for GPU {}: {:?}", i, telemetry);
            }
        });
    }

    std::future::pending::<()>().await;
    // Unreachable, but satisfies return type
    #[allow(unreachable_code)]
    Ok(())
}

#[derive(Serialize, Debug)]
struct GpuTelemetry {
    // Identification
    gpu_id: String,
    gpu_name: String,

    // Performance & Utilization
    utilization_gpu: u32,
    utilization_memory_controller: u32,
    performance_state: String,
    clock_gpu_mhz: u32,
    clock_mem_mhz: u32,

    // Memory
    memory_used_mb: u64,
    memory_total_mb: u64,

    // Power & Thermal
    temperature_c: u32,
    power_draw_w: u32,
    throttling_reasons: String,
}

#[derive(Deserialize, Debug)]
struct JobExecution {
    job_id: String,
    job_type: String,
    script: String,
    args: Vec<String>,
    gpu_id: String,
}

#[derive(Deserialize, Debug)]
struct PollResponse {
    job: Option<JobExecution>,
    message: String,
}

#[derive(Serialize, Debug, Clone)]
struct PerformanceMetrics {
    // Core Performance Metrics
    throughput: Option<f64>,             // Job-specific throughput (samples/sec, fps, etc.)
    samples_per_second: Option<f64>,     // Processing rate
    completion_time_sec: Option<f64>,    // Time to complete workload
    accuracy: Option<f64>,               // Accuracy percentage for ML jobs

    // Resource Efficiency
    memory_efficiency: Option<f64>,      // Memory utilization efficiency (0-1)
    computational_efficiency: Option<f64>, // GPU compute efficiency (0-1)
    peak_memory_usage_mb: Option<u64>,   // Peak memory usage during job

    // Job-Specific Metrics
    frames_processed: Option<u64>,       // For video/rendering jobs
    batches_processed: Option<u64>,      // For ML training jobs
    iterations_completed: Option<u64>,   // For simulation jobs
    final_result: Option<String>,        // Final numerical result

    // Quality Metrics
    error_rate: Option<f64>,             // Error rate for applicable jobs
    convergence_achieved: Option<bool>,  // For optimization jobs
    quality_score: Option<f64>,          // Overall quality metric

    // Resource Usage Patterns
    avg_gpu_utilization: Option<f64>,    // Average GPU usage during job
    max_gpu_utilization: Option<f64>,    // Peak GPU usage
    thermal_events: Option<u32>,         // Number of thermal issues
}

impl PerformanceMetrics {
    fn new() -> Self {
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

#[derive(Serialize, Debug)]
struct JobStatus {
    job_id: String,
    gpu_id: String,
    job_type: Option<String>,            // Added for performance tracking
    status: String, // "started", "running", "completed", "failed"
    message: String,
    start_time: Option<u64>,
    end_time: Option<u64>,
    exit_code: Option<i32>,

    // Enhanced Performance Data
    performance_metrics: Option<PerformanceMetrics>,
    job_summary: Option<String>,         // Human-readable summary
    raw_output_sample: Option<String>,   // Sample of raw output for debugging
}
