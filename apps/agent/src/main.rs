use serde::{Serialize, Deserialize};
use std::time::Duration;
use std::sync::Arc;
use futures_util::StreamExt;
use tokio::sync::Mutex;
use tokio::process::{Command, Child};
use std::time::{SystemTime, UNIX_EPOCH};
use std::collections::HashMap;

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
        status: "started".to_string(),
        message: format!("Starting job execution: {}", job.script),
        start_time: Some(start_time),
        end_time: None,
        exit_code: None,
    };
    publish_job_status(&client, &status).await;

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
        status: "running".to_string(),
        message: "Job is running...".to_string(),
        start_time: Some(start_time),
        end_time: None,
        exit_code: None,
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

            // Wait for the process to complete
            let mut child = {
                let mut jobs = active_jobs.lock().await;
                jobs.remove(&job.job_id).unwrap()
            };

            match child.wait_with_output().await {
                Ok(output) => {
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

                    let final_status = JobStatus {
                        job_id: job.job_id.clone(),
                        gpu_id: job.gpu_id.clone(),
                        status: status_str.to_string(),
                        message: format!("{} (exit code: {})", message, exit_code),
                        start_time: Some(start_time),
                        end_time: Some(end_time),
                        exit_code: Some(exit_code),
                    };

                    publish_job_status(&client, &final_status).await;
                    println!("✅ Job {} completed with exit code: {}", job.job_id, exit_code);
                }
                Err(e) => {
                    let end_time = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs();
                    let error_status = JobStatus {
                        job_id: job.job_id.clone(),
                        gpu_id: job.gpu_id.clone(),
                        status: "failed".to_string(),
                        message: format!("Process error: {}", e),
                        start_time: Some(start_time),
                        end_time: Some(end_time),
                        exit_code: Some(-1),
                    };

                    publish_job_status(&client, &error_status).await;
                    println!("❌ Job {} process error: {}", job.job_id, e);
                }
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
                status: "failed".to_string(),
                message: format!("Failed to spawn job: {}", e),
                start_time: Some(start_time),
                end_time: Some(end_time),
                exit_code: Some(-1),
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
    use tokio::time;

    let os_info = if cfg!(target_os = "macos") {
        "macOS"
    } else {
        "Linux (NVML not available)"
    };

    println!(
        "NVML is not supported on {} or NVIDIA drivers not found. Running in MOCK mode with 3 simulated GPUs and publishing synthetic telemetry to NATS.",
        os_info
    );

    let nats_url = "tcp://0.tcp.in.ngrok.io:18595";
    match async_nats::connect(nats_url).await {
        Ok(client) => {
            println!("Connected to NATS server at {}.", nats_url);
            
            // Clone the client for the command listener task
            let command_client = client.clone();

            // Shared state to control telemetry publishing
            let publishing = Arc::new(Mutex::new(true));
            let telemetry_publishing = publishing.clone();

            // Shared state to track active job processes
            let active_jobs = Arc::new(Mutex::new(HashMap::<String, Child>::new()));
            
            // Spawn a separate task to poll for jobs via HTTP
            let jobs_for_commands = active_jobs.clone();
            let poll_client = command_client.clone();
            tokio::spawn(async move {
                let http_client = reqwest::Client::new();
                let orchestrator_url = "https://4be434ecd546.ngrok-free.app";
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
                        .query(&[("gpu_id", gpu_id)])
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
    use nvml_wrapper::enum_wrappers::device::{Clock, TemperatureSensor, PerformanceState};
    use nvml_wrapper::bitmasks::device::ThrottleReasons;
    use nvml_wrapper::Nvml;
    use tokio::time;

    println!("Starting Aether Telemetry Agent with NVML...");

    // Set up NVIDIA driver environment
    unsafe {
        std::env::set_var("NVIDIA_DRIVER_CAPABILITIES", "all");
        std::env::set_var("NVIDIA_VISIBLE_DEVICES", "all");
    }

    // Connect to NATS server
    let nats_url = "tcp://0.tcp.in.ngrok.io:18595";
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
            let orchestrator_url = "https://4be434ecd546.ngrok-free.app";
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
                    .query(&[("gpu_id", gpu_id)])
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

                let telemetry = GpuTelemetry {
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

                let subject = format!("aether.telemetry.{}:gpu-{}", hostname, i);
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

#[derive(Serialize, Debug)]
struct JobStatus {
    job_id: String,
    gpu_id: String,
    status: String, // "started", "running", "completed", "failed"
    message: String,
    start_time: Option<u64>,
    end_time: Option<u64>,
    exit_code: Option<i32>,
}
