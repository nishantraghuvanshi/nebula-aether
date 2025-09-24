use serde::Serialize;
use std::time::Duration;
use std::sync::Arc;
use futures_util::StreamExt;
use tokio::sync::Mutex;

// Import our new monitor architecture
mod monitor;
use monitor::{create_monitor, metrics_to_telemetry, GpuMonitor};
use monitor::anomaly::AnomalyDetector;
use monitor::performance::PerformanceProfiler;
use monitor::health::HealthMonitor;

// Use new monitor architecture for all platforms
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    run_with_monitor().await
}

// New unified main function using monitor architecture
async fn run_with_monitor() -> Result<(), Box<dyn std::error::Error>> {
    println!("Starting Aether Telemetry Agent with multi-vendor support...");
    
    // Create the appropriate monitor for this system
    let monitor = match create_monitor() {
        Ok(monitor) => {
            println!("Initialized {} successfully", monitor.monitor_name());
            Arc::new(monitor)
        }
        Err(err) => {
            return Err(Box::new(err));
        }
    };
    
    // Detect available GPUs
    let detected_gpus = monitor.detect_gpus()?;
    if detected_gpus.is_empty() {
        return Err("No GPUs detected on this system".into());
    }
    
    println!("Detected {} GPUs:", detected_gpus.len());
    for gpu in &detected_gpus {
        println!("  - {} ({}): {}", gpu.id, gpu.vendor, gpu.name);
        if let Some(arch) = &gpu.architecture {
            println!("    Architecture: {}", arch);
        }
    }
    
    // Initialize advanced monitoring systems
    let mut anomaly_detectors = std::collections::HashMap::new();
    let mut performance_profilers = std::collections::HashMap::new();
    let mut health_monitors = std::collections::HashMap::new();
    
    for gpu in &detected_gpus {
        anomaly_detectors.insert(gpu.id.clone(), AnomalyDetector::new());
        performance_profilers.insert(gpu.id.clone(), PerformanceProfiler::new());
        health_monitors.insert(gpu.id.clone(), HealthMonitor::new());
    }
    
    println!("✅ Advanced monitoring systems initialized:");
    println!("   • Anomaly detection for {} GPUs", anomaly_detectors.len());
    println!("   • Performance profiling for {} GPUs", performance_profilers.len());
    println!("   • Health monitoring for {} GPUs", health_monitors.len());
    
    // Connect to NATS
    let nats_url = "nats://localhost:4222";
    let client = async_nats::connect(nats_url).await?;
            println!("Connected to NATS server at {}.", nats_url);
            
    // Shared state for command handling
    let publishing = Arc::new(Mutex::new(true));
    
    // Spawn command listener for the first GPU (for backward compatibility)
    if let Some(first_gpu) = detected_gpus.first() {
            let command_client = client.clone();
        let command_publishing = publishing.clone();
        let gpu_id = first_gpu.id.clone();
            
            tokio::spawn(async move {
            let mut sub = command_client
                .subscribe(format!("aether.commands.{}", gpu_id))
                .await
                .unwrap();
            println!("Listening for commands on 'aether.commands.{}'", gpu_id);
                
                while let Some(msg) = sub.next().await {
                    let command = String::from_utf8_lossy(&msg.payload);
                    if command.starts_with("execute_job:") {
                        println!("\n>>> Received command to execute job: {} <<<\n", command);
                    } else if command == "enter_sleep" {
                        println!("\n>>> Received command to enter sleep mode. Pausing telemetry for 10s. <<<\n");
                    let mut p = command_publishing.lock().await;
                        *p = false;
                        
                        // Wake up after 10 seconds
                        tokio::time::sleep(tokio::time::Duration::from_secs(10)).await;
                        
                    let mut p = command_publishing.lock().await;
                        *p = true;
                        println!("\n>>> Waking up from sleep mode. Resuming telemetry. <<<\n");
                    }
                }
            });
    }
            
    // Spawn telemetry collection tasks for each GPU
    for gpu in detected_gpus {
        let client = client.clone();
        let monitor = monitor.clone();
        let telemetry_publishing = publishing.clone();
        let gpu_id = gpu.id.clone();
        
        // Clone monitoring systems for this GPU
        let mut anomaly_detector = anomaly_detectors.remove(&gpu_id).unwrap_or_else(AnomalyDetector::new);
        let mut performance_profiler = performance_profilers.remove(&gpu_id).unwrap_or_else(PerformanceProfiler::new);
        let mut health_monitor = health_monitors.remove(&gpu_id).unwrap_or_else(HealthMonitor::new);
        
        tokio::spawn(async move {
            let mut interval = tokio::time::interval(Duration::from_secs(2));
            let mut iteration_count = 0;
            
            loop {
                interval.tick().await;
                iteration_count += 1;
                
                // Check if we should publish telemetry
                if *telemetry_publishing.lock().await {
                    match monitor.collect_telemetry(&gpu_id) {
                        Ok(metrics) => {
                            // Run advanced monitoring
                            let anomalies = anomaly_detector.detect_anomalies(&metrics);
                            let health_assessment = health_monitor.assess_health(&metrics);
                            performance_profiler.add_performance_snapshot(&gpu_id, &metrics);
                            
                            // Convert internal metrics to NATS telemetry format
                            let mut telemetry = metrics_to_telemetry(metrics);
                            
                            // Add enhanced monitoring data
                            telemetry.health_score = Some(health_assessment.health_score);
                            telemetry.health_status = Some(format!("{:?}", health_assessment.health_status));
                            telemetry.anomaly_count = Some(anomalies.len() as u32);
                            telemetry.maintenance_needed = Some(health_assessment.maintenance_needed);
                            
                            match serde_json::to_vec(&telemetry) {
                                Ok(payload) => {
                                    let subject = format!("aether.telemetry.{}", gpu_id);
                                    
                                    if let Err(err) = client.publish(subject.clone(), payload.into()).await {
                                        eprintln!("Failed to publish to NATS: {}", err);
                                        continue;
                                    }
                                    
                                    // Publish anomalies if any
                                    if !anomalies.is_empty() {
                                        let anomaly_subject = format!("aether.anomalies.{}", gpu_id);
                                        if let Ok(anomaly_payload) = serde_json::to_vec(&anomalies) {
                                            let _ = client.publish(anomaly_subject, anomaly_payload.into()).await;
                                        }
                                    }
                                    
                                    // Publish health assessment
                                    let health_subject = format!("aether.health.{}", gpu_id);
                                    if let Ok(health_payload) = serde_json::to_vec(&health_assessment) {
                                        let _ = client.publish(health_subject, health_payload.into()).await;
                                    }
                                    
                                    println!("Published enhanced telemetry to '{}': {} ({}) - Health: {:.1}%, Anomalies: {}", 
                                        subject, telemetry.gpu_name, telemetry.gpu_vendor.as_ref().unwrap_or(&"Unknown".to_string()),
                                        health_assessment.health_score, anomalies.len());
                                }
                                Err(err) => {
                                    eprintln!("Failed to serialize telemetry for {}: {}", gpu_id, err);
                                }
                            }
                        }
                        Err(err) => {
                            eprintln!("Failed to collect telemetry for {}: {}", gpu_id, err);
                        }
                    }
                }
            }
        });
    }

    // Keep the main thread alive
    std::future::pending::<()>().await;
    Ok(())
}

// Old mock mode function removed - now using unified monitor architecture

// Old NVML function removed - now using unified monitor architecture

#[derive(Serialize, Debug)]
struct GpuTelemetry {
    // === EXISTING FIELDS (unchanged for backward compatibility) ===
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
    
    // === NEW OPTIONAL FIELDS (for enhanced telemetry) ===
    // These fields are optional and will be skipped in JSON if None,
    // ensuring backward compatibility with the Go orchestrator
    
    // Vendor & Architecture Information
    #[serde(skip_serializing_if = "Option::is_none")]
    gpu_vendor: Option<String>,           // "NVIDIA", "AMD", "Intel", "Apple"
    #[serde(skip_serializing_if = "Option::is_none")]
    gpu_architecture: Option<String>,     // "Ada Lovelace", "RDNA3", "Xe-HPG", etc.
    
    // Enhanced Performance Metrics
    #[serde(skip_serializing_if = "Option::is_none")]
    utilization_encoder: Option<u32>,     // Video encoder utilization %
    #[serde(skip_serializing_if = "Option::is_none")]
    utilization_decoder: Option<u32>,     // Video decoder utilization %
    
    // PCIe Throughput (for I/O-bound job detection)
    #[serde(skip_serializing_if = "Option::is_none")]
    pcie_tx_throughput_mbps: Option<u32>, // PCIe transmit throughput in MB/s
    #[serde(skip_serializing_if = "Option::is_none")]
    pcie_rx_throughput_mbps: Option<u32>, // PCIe receive throughput in MB/s
    
    // Health & Reliability Metrics
    #[serde(skip_serializing_if = "Option::is_none")]
    ecc_errors_correctable: Option<u32>,  // Correctable ECC errors count
    #[serde(skip_serializing_if = "Option::is_none")]
    ecc_errors_uncorrectable: Option<u32>, // Uncorrectable ECC errors count
    
    // === ADVANCED MONITORING FIELDS ===
    #[serde(skip_serializing_if = "Option::is_none")]
    health_score: Option<f64>,               // Overall health score (0-100)
    #[serde(skip_serializing_if = "Option::is_none")]
    health_status: Option<String>,           // Health status (Excellent, Good, Fair, Poor, Critical, Emergency)
    #[serde(skip_serializing_if = "Option::is_none")]
    anomaly_count: Option<u32>,              // Number of active anomalies
    #[serde(skip_serializing_if = "Option::is_none")]
    performance_score: Option<f64>,          // Overall performance score (0-100)
    #[serde(skip_serializing_if = "Option::is_none")]
    maintenance_needed: Option<bool>,         // Whether maintenance is needed
}
