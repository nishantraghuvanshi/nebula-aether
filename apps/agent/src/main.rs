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
        "NVML is not supported on macOS. Running in MOCK mode and publishing synthetic telemetry to NATS."
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
            
            let mut interval = time::interval(Duration::from_secs(2));
            loop {
                interval.tick().await;
                
                // Check if we should publish telemetry
                if *telemetry_publishing.lock().await {
                    let telemetry = GpuTelemetry {
                        gpu_name: "Mock GPU (macOS)".to_string(),
                        temperature_c: 45,
                        memory_used_mb: 256,
                        memory_total_mb: 24564,
                    };

                    let payload = match serde_json::to_vec(&telemetry) {
                        Ok(p) => p,
                        Err(err) => {
                            eprintln!("Failed to serialize telemetry: {err}");
                            continue;
                        }
                    };

                    let subject = "aether.telemetry.gpu-0";
                    if let Err(err) = client.publish(subject, payload.into()).await {
                        eprintln!("Failed to publish to NATS: {err}");
                        continue;
                    }

                    println!("Published telemetry to '{}': {:?}", subject, telemetry);
                }
            }
        }
        Err(err) => {
            eprintln!("Failed to connect to NATS at {}: {err}", nats_url);
        }
    }
}

#[cfg(not(target_os = "macos"))]
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    use nvml_wrapper::enum_wrappers::device::TemperatureSensor;
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

    // Get the first GPU
    let device = nvml.device_by_index(0)?;

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

    // Start the telemetry loop
    let mut interval = time::interval(Duration::from_secs(2));
    loop {
        interval.tick().await;
        
        // Check if we should publish telemetry
        if *telemetry_publishing.lock().await {
            // Get telemetry data from the GPU
            let gpu_name = device.name()?;
            let temperature_c = device.temperature(TemperatureSensor::Gpu)?;
            let memory_info = device.memory_info()?;
            let memory_used_mb = memory_info.used / 1024 / 1024;
            let memory_total_mb = memory_info.total / 1024 / 1024;

            // Create our telemetry struct
            let telemetry = GpuTelemetry {
                gpu_name,
                temperature_c,
                memory_used_mb,
                memory_total_mb,
            };

            // Convert the struct to a JSON string
            let payload = serde_json::to_vec(&telemetry)?;

            // Publish the JSON payload to a NATS topic
            let subject = "aether.telemetry.gpu-0";
            client.publish(subject, payload.into()).await?;

            println!("Published telemetry to '{}': {:?}", subject, telemetry);
        }
    }
}

#[derive(Serialize, Debug)]
struct GpuTelemetry {
    gpu_name: String,
    temperature_c: u32,
    memory_used_mb: u64,
    memory_total_mb: u64,
}
