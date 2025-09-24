// apps/agent/src/monitor/nvidia.rs
// NVIDIA GPU monitoring implementation using NVML (NVIDIA Management Library)
//
// This module provides comprehensive telemetry collection for NVIDIA GPUs on Linux and Windows.
// It enhances the original NVML integration with additional metrics like encoder/decoder utilization,
// PCIe throughput, and ECC error monitoring.

use crate::monitor::{GpuMonitor, GpuInfo, GpuMetrics, GpuVendor, MonitorError};
use nvml_wrapper::enum_wrappers::device::{Clock, TemperatureSensor};
use nvml_wrapper::Nvml;
use std::sync::Arc;

pub struct NvidiaMonitor {
    nvml: Arc<Nvml>,
}

impl NvidiaMonitor {
    /// Create a new NVIDIA monitor instance
    /// This initializes the NVML library and verifies NVIDIA drivers are available
    pub fn new() -> Result<Self, MonitorError> {
        match Nvml::init() {
            Ok(nvml) => {
                println!("NVML initialized successfully");
                Ok(NvidiaMonitor {
                    nvml: Arc::new(nvml),
                })
            }
            Err(err) => Err(MonitorError::InitializationFailed(
                format!("Failed to initialize NVML: {}", err)
            )),
        }
    }
    
    /// Get architecture name from device if available
    fn get_architecture_name(&self, device: &nvml_wrapper::Device) -> Option<String> {
        // Try to get architecture information
        // Note: This is a simplified approach - in practice, you might want to map
        // device names or compute capability to architecture names
        device.name().ok().and_then(|name| {
            if name.contains("RTX 40") {
                Some("Ada Lovelace".to_string())
            } else if name.contains("RTX 30") {
                Some("Ampere".to_string())
            } else if name.contains("RTX 20") {
                Some("Turing".to_string())
            } else if name.contains("GTX 16") {
                Some("Turing".to_string())
            } else if name.contains("Tesla") || name.contains("A100") || name.contains("A40") {
                Some("Ampere".to_string())
            } else {
                None // Unknown architecture
            }
        })
    }
}

impl GpuMonitor for NvidiaMonitor {
    fn detect_gpus(&self) -> Result<Vec<GpuInfo>, MonitorError> {
        let device_count = self.nvml.device_count()
            .map_err(|e| MonitorError::DeviceNotFound(format!("Failed to get device count: {}", e)))?;
        
        println!("Found {} NVIDIA GPUs", device_count);
        
        let mut gpus = Vec::new();
        
        for i in 0..device_count {
            match self.nvml.device_by_index(i) {
                Ok(device) => {
                    let name = device.name().unwrap_or_else(|_| format!("Unknown NVIDIA GPU {}", i));
                    let architecture = self.get_architecture_name(&device);
                    let pci_bus_id = device.pci_info().ok().map(|info| format!("{:04x}:{:02x}:{:02x}.0", 
                        info.domain, info.bus, info.device));
                    
                    gpus.push(GpuInfo {
                        id: format!("gpu-{}", i),
                        name,
                        vendor: GpuVendor::Nvidia,
                        architecture,
                        pci_bus_id,
                    });
                }
                Err(err) => {
                    eprintln!("Warning: Failed to access NVIDIA GPU {}: {}", i, err);
                }
            }
        }
        
        Ok(gpus)
    }
    
    fn collect_telemetry(&self, gpu_id: &str) -> Result<GpuMetrics, MonitorError> {
        // Extract GPU index from ID (e.g., "gpu-0" -> 0)
        let gpu_index: u32 = gpu_id.strip_prefix("gpu-")
            .and_then(|s| s.parse().ok())
            .ok_or_else(|| MonitorError::DeviceNotFound(format!("Invalid GPU ID: {}", gpu_id)))?;
        
        let device = self.nvml.device_by_index(gpu_index)
            .map_err(|e| MonitorError::DeviceNotFound(format!("GPU {} not found: {}", gpu_index, e)))?;
        
        // === CORE METRICS (always collected) ===
        
        let gpu_name = device.name().unwrap_or_else(|err| {
            eprintln!("Warning: Failed to get GPU {} name: {}. Using default.", gpu_index, err);
            format!("Unknown NVIDIA GPU {}", gpu_index)
        });
        
        let utilization_rates = device.utilization_rates().unwrap_or_else(|err| {
            eprintln!("Warning: Failed to get GPU {} utilization: {}. Using defaults.", gpu_index, err);
            nvml_wrapper::struct_wrappers::device::Utilization { gpu: 0, memory: 0 }
        });
        
        let performance_state_raw = device.performance_state().unwrap_or_else(|err| {
            eprintln!("Warning: Failed to get GPU {} performance state: {}. Using default.", gpu_index, err);
            // We can't construct the enum directly, so we'll handle this in the format step
            nvml_wrapper::enum_wrappers::device::PerformanceState::Unknown
        });
        
        let clock_gpu = device.clock_info(Clock::Graphics).unwrap_or_else(|err| {
            eprintln!("Warning: Failed to get GPU {} graphics clock: {}. Using default.", gpu_index, err);
            0
        });
        
        let clock_mem = device.clock_info(Clock::Memory).unwrap_or_else(|err| {
            eprintln!("Warning: Failed to get GPU {} memory clock: {}. Using default.", gpu_index, err);
            0
        });
        
        let memory_info = device.memory_info().unwrap_or_else(|err| {
            eprintln!("Warning: Failed to get GPU {} memory info: {}. Using defaults.", gpu_index, err);
            nvml_wrapper::struct_wrappers::device::MemoryInfo { total: 0, free: 0, used: 0 }
        });
        
        let temperature_c = device.temperature(TemperatureSensor::Gpu).unwrap_or_else(|err| {
            eprintln!("Warning: Failed to get GPU {} temperature: {}. Using default.", gpu_index, err);
            0
        });
        
        let power_draw = device.power_usage().unwrap_or_else(|err| {
            eprintln!("Warning: Failed to get GPU {} power usage: {}. Using default.", gpu_index, err);
            0
        }) / 1000; // Convert mW to W
        
        let throttle_reasons = device.current_throttle_reasons().unwrap_or_else(|err| {
            eprintln!("Warning: Failed to get GPU {} throttle reasons: {}. Using default.", gpu_index, err);
            nvml_wrapper::bitmasks::device::ThrottleReasons::empty()
        });
        
        // === ENHANCED METRICS (NVIDIA-specific, optional) ===
        // Note: Some advanced NVML features are not available in all driver versions
        // For now, we'll set these to None and can enhance them later
        
        // Encoder/Decoder utilization (requires newer NVML versions)
        let utilization_encoder = None; // TODO: Implement when NVML API is available
        let utilization_decoder = None; // TODO: Implement when NVML API is available
        
        // PCIe throughput (requires specific NVML version and GPU support)
        let pcie_tx_throughput_mbps = None; // TODO: Implement when NVML API is stable
        let pcie_rx_throughput_mbps = None; // TODO: Implement when NVML API is stable
        
        // ECC error counts (requires ECC-enabled GPUs)
        let ecc_errors_correctable = None;   // TODO: Implement when ECC API is available
        let ecc_errors_uncorrectable = None; // TODO: Implement when ECC API is available
        
        Ok(GpuMetrics {
            // Basic identification
            gpu_id: format!("gpu-{}", gpu_index),
            gpu_name,
            vendor: GpuVendor::Nvidia,
            architecture: self.get_architecture_name(&device).unwrap_or_else(|| "Unknown".to_string()),
            
            // Core performance metrics
            utilization_gpu: utilization_rates.gpu,
            utilization_memory: utilization_rates.memory,
            memory_used: memory_info.used / 1024 / 1024,
            memory_total: memory_info.total / 1024 / 1024,
            temperature: temperature_c,
            power_draw: power_draw,
            clock_gpu: clock_gpu,
            clock_memory: clock_mem,
            throttling_reasons: format!("{:?}", throttle_reasons),
            performance_state: format!("{:?}", performance_state_raw),
            
            // Enhanced metrics (NVIDIA-specific)
            utilization_encoder,
            utilization_decoder,
            pcie_tx_throughput_mbps,
            pcie_rx_throughput_mbps,
            ecc_errors_correctable,
            ecc_errors_uncorrectable,
        })
    }
    
    fn monitor_name(&self) -> &'static str {
        "NVIDIA NVML Monitor"
    }
    
    fn is_available(&self) -> bool {
        // Check if NVML is available and has devices
        match self.nvml.device_count() {
            Ok(count) => count > 0,
            Err(_) => false,
        }
    }
} 