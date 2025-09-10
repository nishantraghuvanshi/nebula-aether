use serde::Serialize;
use std::time::Duration;
use futures_util::StreamExt;
use tokio::sync::Mutex;
use std::sync::Arc;

#[cfg(target_os = "macos")]
#[tokio::main]
async fn main() {
    use tokio::time;

    println!(
        "NVML is not supported on macOS. Running in MOCK mode with 3 simulated GPUs and publishing synthetic telemetry to NATS."
    );

    let nats_url = "nats://localhost:4222";
    match async_nats::connect(nats_url).await {
        Ok(client) => {
            println!("Connected to NATS server at {}.", nats_url);
            
            // Clone the client for the command listener task
            let command_client = client.clone();
            
            // Shared state to control telemetry publishing
            let publishing = Arc::new(Mutex::new(true));
            let telemetry_publishing = publishing.clone();
            
            // Spawn a separate task to listen for commands
            tokio::spawn(async move {
                let mut sub = command_client.subscribe("aether.commands.gpu-0").await.unwrap();
                println!("Listening for commands on 'aether.commands.gpu-0'");
                
                while let Some(msg) = sub.next().await {
                    let command = String::from_utf8_lossy(&msg.payload);
                    if command.starts_with("execute_job:") {
                        println!("\n>>> Received command to execute job: {} <<<\n", command);
                    } else if command == "enter_sleep" {
                        println!("\n>>> Received command to enter sleep mode. Pausing telemetry for 10s. <<<\n");
                        let mut p = publishing.lock().await;
                        *p = false;
                        
                        // Wake up after 10 seconds
                        tokio::time::sleep(tokio::time::Duration::from_secs(10)).await;
                        
                        let mut p = publishing.lock().await;
                        *p = true;
                        println!("\n>>> Waking up from sleep mode. Resuming telemetry. <<<\n");
                    }
                }
            });
            
            // Simulate 3 GPUs for testing multi-GPU functionality
            let gpu_configs = vec![
                ("gpu-0", "Mock RTX 4090", 45, 35, 256, 65),
                ("gpu-1", "Mock RTX 4080", 52, 28, 512, 55),
                ("gpu-2", "Mock RTX 4070", 38, 42, 128, 45),
            ];

            for (gpu_id, gpu_name, base_temp, base_util, base_mem, base_power) in gpu_configs {
                let client = client.clone();
                let telemetry_publishing = telemetry_publishing.clone();
                
                tokio::spawn(async move {
                    let mut interval = time::interval(Duration::from_secs(2));
                    loop {
                        interval.tick().await;
                        
                        // Check if we should publish telemetry
                        if *telemetry_publishing.lock().await {
                            // Add some variation to make it more realistic
                            let temp_variation = (std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_secs() % 10) as u32;
                            let util_variation = (std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_secs() % 15) as u32;
                            
                            let telemetry = GpuTelemetry {
                                // Identification
                                gpu_name: gpu_name.to_string(),
                                
                                // Performance & Utilization
                                utilization_gpu: base_util + util_variation,
                                utilization_memory_controller: base_util + util_variation - 5,
                                performance_state: "P2".to_string(),
                                clock_gpu_mhz: 1200 + (util_variation * 10),
                                clock_mem_mhz: 5000 + (util_variation * 50),

                                // Memory
                                memory_used_mb: (base_mem + (util_variation * 10)) as u64,
                                memory_total_mb: 24564,

                                // Power & Thermal
                                temperature_c: base_temp + temp_variation,
                                power_draw_w: base_power + (temp_variation / 2),
                                throttling_reasons: if base_temp + temp_variation > 80 { "Thermal".to_string() } else { "None".to_string() },
                            };

                            let payload = match serde_json::to_vec(&telemetry) {
                                Ok(p) => p,
                                Err(err) => {
                                    eprintln!("Failed to serialize telemetry: {err}");
                                    continue;
                                }
                            };

                            let subject = format!("aether.telemetry.{}", gpu_id);

                            if let Err(err) = client.publish(subject.clone(), payload.into()).await { // <-- ADD & HERE
                                eprintln!("Failed to publish to NATS: {err}");
                                continue;
                            }

                            println!("Published telemetry to '{}': {:?}", subject, telemetry);
                        }
                    }
                });
            }
            
            // Keep the main thread alive
            std::future::pending::<()>().await;
        }
        Err(err) => {
            eprintln!("Failed to connect to NATS at {}: {err}", nats_url);
        }
    }
}

#[cfg(not(target_os = "macos"))]
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    use nvml_wrapper::enum_wrappers::device::{Clock, TemperatureSensor};
    use nvml_wrapper::Nvml;
    use tokio::time;

    println!("Starting Aether Telemetry Agent...");

    // Connect to NATS server
    let nats_url = "nats://localhost:4222";
    let client = async_nats::connect(nats_url).await?;
    println!("Connected to NATS server at {}.", nats_url);

    // Initialize the NVML library
    let nvml = Nvml::init()?;
    println!("NVML initialized.");

    let device_count = nvml.device_count()?;
    println!("Found {} NVIDIA GPUs.", device_count);

    for i in 0..device_count {
        let client = client.clone();
        let nvml = nvml.clone();

        tokio::spawn(async move {
            let device = nvml.device_by_index(i).unwrap();
            let mut interval = time::interval(Duration::from_secs(2));

            loop {
                interval.tick().await;

                // --- Get All Data Points ---
                let gpu_name = device.name().unwrap();
                let utilization_rates = device.utilization_rates().unwrap();
                let perf_state = device.performance_state().unwrap();
                let clock_gpu = device.clock_info(Clock::Graphics).unwrap();
                let clock_mem = device.clock_info(Clock::Memory).unwrap();
                let memory_info = device.memory_info().unwrap();
                let temperature_c = device.temperature(TemperatureSensor::Gpu).unwrap();
                let power_draw = device.power_usage().unwrap() / 1000; // mW -> W
                let throttle_reasons = device.current_throttle_reasons().unwrap();

                let telemetry = GpuTelemetry {
                    gpu_name,
                    utilization_gpu: utilization_rates.gpu,
                    utilization_memory_controller: utilization_rates.memory,
                    performance_state: format!("{:?}", perf_state),
                    clock_gpu_mhz: clock_gpu,
                    clock_mem_mhz: clock_mem,
                    memory_used_mb: memory_info.used / 1024 / 1024,
                    memory_total_mb: memory_info.total / 1024 / 1024,
                    temperature_c,
                    power_draw_w: power_draw,
                    throttling_reasons: format!("{:?}", throttle_reasons),
                };

                let subject = format!("aether.telemetry.gpu-{}", i);
                let payload = serde_json::to_vec(&telemetry).unwrap();
                if let Err(err) = client.publish(&subject, payload.into()).await {
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
