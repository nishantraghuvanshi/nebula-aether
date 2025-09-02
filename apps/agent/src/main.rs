use serde::Serialize;
use std::time::Duration;

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
            let mut interval = time::interval(Duration::from_secs(2));
            loop {
                interval.tick().await;

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

    // Start the telemetry loop
    let mut interval = time::interval(Duration::from_secs(2));
    loop {
        interval.tick().await;

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

#[derive(Serialize, Debug)]
struct GpuTelemetry {
    gpu_name: String,
    temperature_c: u32,
    memory_used_mb: u64,
    memory_total_mb: u64,
}
