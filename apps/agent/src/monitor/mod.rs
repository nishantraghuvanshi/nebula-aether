// apps/agent/src/monitor/mod.rs
// Multi-vendor GPU monitoring architecture
//
// This module provides a unified interface for collecting telemetry from different GPU vendors
// (NVIDIA, AMD, Intel, Apple) while maintaining a consistent data contract with the orchestrator.

use serde::{Serialize, Deserialize};
use std::error::Error;
use std::fmt;

// Re-export vendor-specific modules based on platform and feature flags
#[cfg(any(target_os = "linux", target_os = "windows"))]
#[cfg(feature = "nvidia")]
pub mod nvidia;

#[cfg(target_os = "linux")]
#[cfg(feature = "amd")]
pub mod amd;

#[cfg(target_os = "linux")]
#[cfg(feature = "intel")]
pub mod intel;

#[cfg(target_os = "macos")]
pub mod macos;

// Advanced monitoring modules (always available)
pub mod anomaly;
pub mod performance;
pub mod health;

/// Unified error type for all GPU monitoring operations
#[derive(Debug)]
pub enum MonitorError {
    InitializationFailed(String),
    DeviceNotFound(String),
    TelemetryCollectionFailed(String),
    UnsupportedOperation(String),
}

impl fmt::Display for MonitorError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            MonitorError::InitializationFailed(msg) => write!(f, "Monitor initialization failed: {}", msg),
            MonitorError::DeviceNotFound(msg) => write!(f, "GPU device not found: {}", msg),
            MonitorError::TelemetryCollectionFailed(msg) => write!(f, "Telemetry collection failed: {}", msg),
            MonitorError::UnsupportedOperation(msg) => write!(f, "Unsupported operation: {}", msg),
        }
    }
}

impl Error for MonitorError {}

/// GPU vendor enumeration
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum GpuVendor {
    Nvidia,
    Amd,
    Intel,
    Apple,
}

impl fmt::Display for GpuVendor {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            GpuVendor::Nvidia => write!(f, "NVIDIA"),
            GpuVendor::Amd => write!(f, "AMD"),
            GpuVendor::Intel => write!(f, "Intel"),
            GpuVendor::Apple => write!(f, "Apple"),
        }
    }
}

/// Basic GPU information for device discovery
#[derive(Debug, Clone)]
pub struct GpuInfo {
    pub id: String,              // Unique identifier (e.g., "gpu-0", "gpu-1")
    pub name: String,            // Human-readable name (e.g., "RTX 4090")
    pub vendor: GpuVendor,       // GPU vendor
    pub architecture: Option<String>, // Architecture name if available
    pub pci_bus_id: Option<String>,   // PCI bus identifier
}

/// Comprehensive GPU metrics structure
/// This is the internal representation that gets converted to GpuTelemetry for NATS
#[derive(Debug, Clone)]
pub struct GpuMetrics {
    // Basic identification
    pub gpu_id: String,                 // Unique GPU identifier
    pub gpu_name: String,               // Human-readable name
    pub vendor: GpuVendor,
    pub architecture: String,            // Architecture name
    
    // Core performance metrics (always available)
    pub utilization_gpu: u32,           // GPU utilization percentage (0-100)
    pub utilization_memory: u32,         // Memory controller utilization (0-100)
    pub memory_used: u64,               // Used VRAM in MB
    pub memory_total: u64,              // Total VRAM in MB
    pub temperature: u32,               // GPU temperature in Celsius
    pub power_draw: u32,                // Power consumption in Watts
    pub clock_gpu: u32,                 // GPU core clock in MHz
    pub clock_memory: u32,              // Memory clock in MHz
    pub throttling_reasons: String,     // Throttling status description
    pub performance_state: String,      // Performance state (P0, P2, etc.)
    
    // Enhanced metrics (vendor-specific, may be None)
    pub utilization_encoder: Option<u32>,     // Video encoder utilization %
    pub utilization_decoder: Option<u32>,     // Video decoder utilization %
    pub pcie_tx_throughput_mbps: Option<u32>, // PCIe transmit throughput
    pub pcie_rx_throughput_mbps: Option<u32>, // PCIe receive throughput
    pub ecc_errors_correctable: Option<u32>,  // Correctable ECC errors
    pub ecc_errors_uncorrectable: Option<u32>, // Uncorrectable ECC errors
}

/// Main trait that all vendor-specific monitors must implement
pub trait GpuMonitor: Send + Sync {
    /// Initialize the monitoring system and detect available GPUs
    /// Returns a list of GPU information for all detectable devices
    fn detect_gpus(&self) -> Result<Vec<GpuInfo>, MonitorError>;
    
    /// Collect comprehensive telemetry data for a specific GPU
    /// The gpu_id should match one returned by detect_gpus()
    fn collect_telemetry(&self, gpu_id: &str) -> Result<GpuMetrics, MonitorError>;
    
    /// Get a human-readable name for this monitor implementation
    fn monitor_name(&self) -> &'static str;
    
    /// Check if this monitor can run on the current system
    fn is_available(&self) -> bool;
}

/// Factory function to create the appropriate monitor for the current system
pub fn create_monitor() -> Result<Box<dyn GpuMonitor>, MonitorError> {
    // Try monitors in order of preference/capability
    
    #[cfg(any(target_os = "linux", target_os = "windows"))]
    #[cfg(feature = "nvidia")]
    {
        let nvidia_monitor = nvidia::NvidiaMonitor::new();
        if let Ok(monitor) = nvidia_monitor {
            if monitor.is_available() {
                println!("Using NVIDIA GPU monitor");
                return Ok(Box::new(monitor));
            }
        }
    }
    
    #[cfg(target_os = "linux")]
    #[cfg(feature = "amd")]
    {
        let amd_monitor = amd::AmdMonitor::new();
        if let Ok(monitor) = amd_monitor {
            if monitor.is_available() {
                println!("Using AMD GPU monitor");
                return Ok(Box::new(monitor));
            }
        }
    }
    
    #[cfg(target_os = "linux")]
    #[cfg(feature = "intel")]
    {
        let intel_monitor = intel::IntelMonitor::new();
        if let Ok(monitor) = intel_monitor {
            if monitor.is_available() {
                println!("Using Intel GPU monitor");
                return Ok(Box::new(monitor));
            }
        }
    }
    
    #[cfg(target_os = "macos")]
    {
        let macos_monitor = macos::MacosMonitor::new();
        if let Ok(monitor) = macos_monitor {
            if monitor.is_available() {
                println!("Using macOS GPU monitor");
                return Ok(Box::new(monitor));
            }
        }
    }
    
    Err(MonitorError::InitializationFailed(
        "No compatible GPU monitor found for this system".to_string()
    ))
}

/// Convert internal GpuMetrics to the external GpuTelemetry format for NATS
pub fn metrics_to_telemetry(metrics: GpuMetrics) -> crate::GpuTelemetry {
    crate::GpuTelemetry {
        // Map core fields (always present)
        gpu_name: metrics.gpu_name,
        utilization_gpu: metrics.utilization_gpu,
        utilization_memory_controller: metrics.utilization_memory,
        performance_state: metrics.performance_state,
        clock_gpu_mhz: metrics.clock_gpu,
        clock_mem_mhz: metrics.clock_memory,
        memory_used_mb: metrics.memory_used,
        memory_total_mb: metrics.memory_total,
        temperature_c: metrics.temperature,
        power_draw_w: metrics.power_draw,
        throttling_reasons: metrics.throttling_reasons,
        
        // Map enhanced fields (optional)
        gpu_vendor: Some(metrics.vendor.to_string()),
        gpu_architecture: Some(metrics.architecture),
        utilization_encoder: metrics.utilization_encoder,
        utilization_decoder: metrics.utilization_decoder,
        pcie_tx_throughput_mbps: metrics.pcie_tx_throughput_mbps,
        pcie_rx_throughput_mbps: metrics.pcie_rx_throughput_mbps,
        ecc_errors_correctable: metrics.ecc_errors_correctable,
        ecc_errors_uncorrectable: metrics.ecc_errors_uncorrectable,
        
        // Advanced monitoring fields (optional)
        health_score: None,
        health_status: None,
        anomaly_count: None,
        performance_score: None,
        maintenance_needed: None,
    }
} 