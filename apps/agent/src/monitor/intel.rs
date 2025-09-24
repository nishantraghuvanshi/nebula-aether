// apps/agent/src/monitor/intel.rs
// Intel GPU monitoring implementation using intel_gpu_top
//
// This module provides comprehensive telemetry collection for Intel GPUs on Linux
// using the intel_gpu_top utility with JSON output parsing.

use crate::monitor::{GpuMonitor, GpuInfo, GpuMetrics, GpuVendor, MonitorError};
use std::process::Command;
use std::collections::HashMap;
use serde_json::Value;

pub struct IntelMonitor {
    intel_gpu_top_path: String,
    device_count: u32,
    device_info: HashMap<String, IntelDeviceInfo>,
    capabilities: IntelCapabilities,
}

#[derive(Debug, Clone)]
struct IntelDeviceInfo {
    device_id: u32,
    name: String,
    architecture: String,
    memory_total: u64,
    memory_type: String,
    execution_units: u32,
    max_frequency: u32,
    memory_frequency: u32,
}

#[derive(Debug, Clone)]
struct IntelCapabilities {
    supports_power_management: bool,
    supports_frequency_control: bool,
    supports_memory_control: bool,
    supports_temperature_monitoring: bool,
    max_power_limit: u32,
}

impl IntelMonitor {
    pub fn new() -> Result<Self, MonitorError> {
        // Check if intel_gpu_top is available
        let intel_gpu_top_path = Self::find_intel_gpu_top()?;
        
        // Get device count
        let device_count = Self::get_device_count(&intel_gpu_top_path)?;
        
        if device_count == 0 {
            return Err(MonitorError::InitializationFailed(
                "No Intel GPUs detected by intel_gpu_top".to_string()
            ));
        }
        
        // Initialize device info
        let mut device_info = HashMap::new();
        for i in 0..device_count {
            let device_info_data = Self::get_device_info(&intel_gpu_top_path, i)?;
            device_info.insert(format!("intel_gpu_{}", i), device_info_data);
        }
        
        // Get capabilities
        let capabilities = Self::get_capabilities(&intel_gpu_top_path)?;
        
        Ok(IntelMonitor {
            intel_gpu_top_path,
            device_count,
            device_info,
            capabilities,
        })
    }
    
    fn find_intel_gpu_top() -> Result<String, MonitorError> {
        // Try common intel_gpu_top paths
        let possible_paths = vec![
            "/usr/bin/intel_gpu_top",
            "/usr/local/bin/intel_gpu_top",
            "/opt/intel/bin/intel_gpu_top",
            "intel_gpu_top", // Try PATH
        ];
        
        for path in possible_paths {
            if Self::check_command_exists(path) {
                return Ok(path.to_string());
            }
        }
        
        Err(MonitorError::InitializationFailed(
            "intel_gpu_top not found. Please install Intel GPU drivers and ensure intel_gpu_top is in PATH".to_string()
        ))
    }
    
    fn check_command_exists(command: &str) -> bool {
        Command::new("which")
            .arg(command)
            .output()
            .map(|output| output.status.success())
            .unwrap_or(false)
    }
    
    fn get_device_count(intel_gpu_top_path: &str) -> Result<u32, MonitorError> {
        let output = Command::new(intel_gpu_top_path)
            .arg("-l")
            .output()
            .map_err(|e| MonitorError::InitializationFailed(
                format!("Failed to execute intel_gpu_top: {}", e)
            ))?;
        
        if !output.status.success() {
            return Err(MonitorError::InitializationFailed(
                "Failed to get device count from intel_gpu_top".to_string()
            ));
        }
        
        let output_str = String::from_utf8_lossy(&output.stdout);
        let lines: Vec<&str> = output_str.lines().collect();
        
        // Count device lines (skip header lines)
        let device_count = lines.iter()
            .filter(|line| line.contains("GPU") && line.contains(":"))
            .count() as u32;
        
        Ok(device_count)
    }
    
    fn get_device_info(intel_gpu_top_path: &str, device_id: u32) -> Result<IntelDeviceInfo, MonitorError> {
        // Get device information using JSON output
        let output = Command::new(intel_gpu_top_path)
            .arg("-J")
            .arg("-d")
            .arg(device_id.to_string())
            .output()
            .map_err(|e| MonitorError::InitializationFailed(
                format!("Failed to get device info: {}", e)
            ))?;
        
        if !output.status.success() {
            return Err(MonitorError::InitializationFailed(
                "Failed to get device info from intel_gpu_top".to_string()
            ));
        }
        
        let json_str = String::from_utf8_lossy(&output.stdout);
        let json: Value = serde_json::from_str(&json_str)
            .map_err(|e| MonitorError::InitializationFailed(
                format!("Failed to parse JSON from intel_gpu_top: {}", e)
            ))?;
        
        // Extract device information
        let name = json["device"]["name"]
            .as_str()
            .unwrap_or("Unknown Intel GPU")
            .to_string();
        
        let architecture = Self::detect_intel_architecture(&name);
        
        // Get memory information
        let memory_total = json["device"]["memory"]["total"]
            .as_u64()
            .unwrap_or(8192); // Default 8GB
        
        // Get frequency information
        let max_frequency = json["device"]["frequency"]["max"]
            .as_u64()
            .unwrap_or(1000) as u32;
        
        let memory_frequency = json["device"]["memory"]["frequency"]
            .as_u64()
            .unwrap_or(1000) as u32;
        
        // Estimate execution units
        let execution_units = Self::estimate_execution_units(&name);
        
        Ok(IntelDeviceInfo {
            device_id,
            name,
            architecture,
            memory_total,
            memory_type: "LPDDR5".to_string(), // Default for modern Intel GPUs
            execution_units,
            max_frequency,
            memory_frequency,
        })
    }
    
    fn get_capabilities(intel_gpu_top_path: &str) -> Result<IntelCapabilities, MonitorError> {
        // Check power management support
        let power_output = Command::new(intel_gpu_top_path)
            .arg("-J")
            .arg("-p")
            .output();
        
        let supports_power_management = power_output.is_ok() && power_output.unwrap().status.success();
        
        // Check frequency control support
        let freq_output = Command::new(intel_gpu_top_path)
            .arg("-J")
            .arg("-f")
            .output();
        
        let supports_frequency_control = freq_output.is_ok() && freq_output.unwrap().status.success();
        
        // Check memory control support
        let mem_output = Command::new(intel_gpu_top_path)
            .arg("-J")
            .arg("-m")
            .output();
        
        let supports_memory_control = mem_output.is_ok() && mem_output.unwrap().status.success();
        
        // Check temperature monitoring support
        let temp_output = Command::new(intel_gpu_top_path)
            .arg("-J")
            .arg("-t")
            .output();
        
        let supports_temperature_monitoring = temp_output.is_ok() && temp_output.unwrap().status.success();
        
        Ok(IntelCapabilities {
            supports_power_management,
            supports_frequency_control,
            supports_memory_control,
            supports_temperature_monitoring,
            max_power_limit: 100, // Default for Intel GPUs
        })
    }
    
    fn detect_intel_architecture(name: &str) -> String {
        let name_lower = name.to_lowercase();
        
        if name_lower.contains("arc") && name_lower.contains("a770") {
            "Xe-HPG".to_string()
        } else if name_lower.contains("arc") && name_lower.contains("a750") {
            "Xe-HPG".to_string()
        } else if name_lower.contains("arc") && name_lower.contains("a580") {
            "Xe-HPG".to_string()
        } else if name_lower.contains("iris xe") {
            "Xe-LP".to_string()
        } else if name_lower.contains("uhd") && name_lower.contains("770") {
            "Xe-LP".to_string()
        } else if name_lower.contains("uhd") && name_lower.contains("750") {
            "Xe-LP".to_string()
        } else if name_lower.contains("uhd") && name_lower.contains("630") {
            "Gen9".to_string()
        } else if name_lower.contains("uhd") && name_lower.contains("620") {
            "Gen9".to_string()
        } else if name_lower.contains("hd") && name_lower.contains("630") {
            "Gen9".to_string()
        } else if name_lower.contains("hd") && name_lower.contains("620") {
            "Gen9".to_string()
        } else {
            "Unknown".to_string()
        }
    }
    
    fn estimate_execution_units(name: &str) -> u32 {
        let name_lower = name.to_lowercase();
        
        if name_lower.contains("arc a770") {
            32
        } else if name_lower.contains("arc a750") {
            28
        } else if name_lower.contains("arc a580") {
            24
        } else if name_lower.contains("iris xe") {
            96
        } else if name_lower.contains("uhd 770") {
            32
        } else if name_lower.contains("uhd 750") {
            32
        } else if name_lower.contains("uhd 630") {
            24
        } else if name_lower.contains("uhd 620") {
            24
        } else if name_lower.contains("hd 630") {
            24
        } else if name_lower.contains("hd 620") {
            24
        } else {
            24 // Default estimate
        }
    }
}

impl GpuMonitor for IntelMonitor {
    fn detect_gpus(&self) -> Result<Vec<GpuInfo>, MonitorError> {
        let mut gpus = Vec::new();
        
        for (gpu_id, device_info) in &self.device_info {
            let gpu_info = GpuInfo {
                id: gpu_id.clone(),
                name: device_info.name.clone(),
                vendor: GpuVendor::Intel,
                architecture: device_info.architecture.clone(),
                memory_total: device_info.memory_total,
                capabilities: vec![
                    "compute".to_string(),
                    "graphics".to_string(),
                    if self.capabilities.supports_power_management { "power_management".to_string() } else { "".to_string() },
                    if self.capabilities.supports_frequency_control { "frequency_control".to_string() } else { "".to_string() },
                ].into_iter().filter(|s| !s.is_empty()).collect(),
            };
            
            gpus.push(gpu_info);
        }
        
        Ok(gpus)
    }
    
    fn collect_telemetry(&self, gpu_id: &str) -> Result<GpuMetrics, MonitorError> {
        let device_info = self.device_info.get(gpu_id)
            .ok_or_else(|| MonitorError::TelemetryCollectionFailed(
                format!("GPU {} not found", gpu_id)
            ))?;
        
        let device_id = device_info.device_id;
        
        // Get telemetry using JSON output
        let output = Command::new(&self.intel_gpu_top_path)
            .arg("-J")
            .arg("-d")
            .arg(device_id.to_string())
            .output()
            .map_err(|e| MonitorError::TelemetryCollectionFailed(
                format!("Failed to get telemetry: {}", e)
            ))?;
        
        if !output.status.success() {
            return Err(MonitorError::TelemetryCollectionFailed(
                "Failed to get telemetry from intel_gpu_top".to_string()
            ));
        }
        
        let json_str = String::from_utf8_lossy(&output.stdout);
        let json: Value = serde_json::from_str(&json_str)
            .map_err(|e| MonitorError::TelemetryCollectionFailed(
                format!("Failed to parse telemetry JSON: {}", e)
            ))?;
        
        // Extract telemetry data
        let gpu_util = json["device"]["utilization"]["gpu"]
            .as_u64()
            .unwrap_or(0) as u32;
        
        let memory_util = json["device"]["utilization"]["memory"]
            .as_u64()
            .unwrap_or(0) as u32;
        
        let memory_used = json["device"]["memory"]["used"]
            .as_u64()
            .unwrap_or(0);
        
        let temperature = json["device"]["temperature"]
            .as_u64()
            .unwrap_or(50) as u32;
        
        let power_draw = json["device"]["power"]
            .as_u64()
            .unwrap_or(50) as u32;
        
        let current_gpu_clock = json["device"]["frequency"]["current"]
            .as_u64()
            .unwrap_or(device_info.max_frequency as u64) as u32;
        
        let current_memory_clock = json["device"]["memory"]["frequency"]
            .as_u64()
            .unwrap_or(device_info.memory_frequency as u64) as u32;
        
        Ok(GpuMetrics {
            gpu_id: gpu_id.to_string(),
            gpu_name: device_info.name.clone(),
            utilization_gpu: gpu_util,
            utilization_memory: memory_util,
            utilization_encoder: None, // Intel GPUs don't typically expose encoder/decoder utilization
            utilization_decoder: None,
            memory_used,
            memory_total: device_info.memory_total,
            temperature,
            power_draw,
            clock_gpu: current_gpu_clock,
            clock_memory: current_memory_clock,
            throttling_reasons: "".to_string(), // Intel GPUs don't provide throttling reasons
            performance_state: "Unknown".to_string(), // Intel GPUs don't provide performance state
            pcie_tx_throughput_mbps: None, // Not available in intel_gpu_top
            pcie_rx_throughput_mbps: None,
            ecc_errors_correctable: None, // Intel GPUs don't typically have ECC
            ecc_errors_uncorrectable: None,
            vendor: GpuVendor::Intel,
            architecture: device_info.architecture.clone(),
        })
    }
    
    fn monitor_name(&self) -> &'static str {
        "Intel GPU Top Monitor"
    }
    
    fn is_available(&self) -> bool {
        self.device_count > 0
    }
} 