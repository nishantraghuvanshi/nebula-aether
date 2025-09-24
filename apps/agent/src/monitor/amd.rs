// apps/agent/src/monitor/amd.rs
// AMD GPU monitoring implementation using ROCm SMI
//
// This module provides comprehensive telemetry collection for AMD GPUs on Linux
// using the ROCm System Management Interface (SMI) library.

use crate::monitor::{GpuMonitor, GpuInfo, GpuMetrics, GpuVendor, MonitorError};
use std::process::Command;
use std::collections::HashMap;
use std::time::SystemTime;

pub struct AmdMonitor {
    rocm_smi_path: String,
    device_count: u32,
    device_info: HashMap<String, AmdDeviceInfo>,
    capabilities: AmdCapabilities,
}

#[derive(Debug, Clone)]
struct AmdDeviceInfo {
    device_id: u32,
    name: String,
    architecture: String,
    memory_total: u64,
    memory_type: String,
    compute_units: u32,
    max_clock: u32,
    memory_clock: u32,
}

#[derive(Debug, Clone)]
struct AmdCapabilities {
    supports_ecc: bool,
    supports_power_management: bool,
    supports_clock_control: bool,
    supports_fan_control: bool,
    max_power_limit: u32,
}

impl AmdMonitor {
    pub fn new() -> Result<Self, MonitorError> {
        // Check if rocm-smi is available
        let rocm_smi_path = Self::find_rocm_smi()?;
        
        // Get device count
        let device_count = Self::get_device_count(&rocm_smi_path)?;
        
        if device_count == 0 {
            return Err(MonitorError::InitializationFailed(
                "No AMD GPUs detected by ROCm SMI".to_string()
            ));
        }
        
        // Initialize device info
        let mut device_info = HashMap::new();
        for i in 0..device_count {
            let device_info_data = Self::get_device_info(&rocm_smi_path, i)?;
            device_info.insert(format!("amd_gpu_{}", i), device_info_data);
        }
        
        // Get capabilities
        let capabilities = Self::get_capabilities(&rocm_smi_path)?;
        
        Ok(AmdMonitor {
            rocm_smi_path,
            device_count,
            device_info,
            capabilities,
        })
    }
    
    fn find_rocm_smi() -> Result<String, MonitorError> {
        // Try common ROCm SMI paths
        let possible_paths = vec![
            "/opt/rocm/bin/rocm-smi",
            "/usr/bin/rocm-smi",
            "/usr/local/bin/rocm-smi",
            "rocm-smi", // Try PATH
        ];
        
        for path in possible_paths {
            if Self::check_command_exists(path) {
                return Ok(path.to_string());
            }
        }
        
        Err(MonitorError::InitializationFailed(
            "ROCm SMI not found. Please install ROCm drivers and ensure rocm-smi is in PATH".to_string()
        ))
    }
    
    fn check_command_exists(command: &str) -> bool {
        Command::new("which")
            .arg(command)
            .output()
            .map(|output| output.status.success())
            .unwrap_or(false)
    }
    
    fn get_device_count(rocm_smi_path: &str) -> Result<u32, MonitorError> {
        let output = Command::new(rocm_smi_path)
            .arg("--showproductname")
            .arg("--csv")
            .output()
            .map_err(|e| MonitorError::InitializationFailed(
                format!("Failed to execute rocm-smi: {}", e)
            ))?;
        
        if !output.status.success() {
            return Err(MonitorError::InitializationFailed(
                "Failed to get device count from ROCm SMI".to_string()
            ));
        }
        
        let output_str = String::from_utf8_lossy(&output.stdout);
        let lines: Vec<&str> = output_str.lines().collect();
        
        // Count non-header lines (skip first line which is usually headers)
        let device_count = if lines.len() > 1 {
            lines.len() as u32 - 1
        } else {
            0
        };
        
        Ok(device_count)
    }
    
    fn get_device_info(rocm_smi_path: &str, device_id: u32) -> Result<AmdDeviceInfo, MonitorError> {
        // Get device name
        let name_output = Command::new(rocm_smi_path)
            .arg("--showproductname")
            .arg("--csv")
            .arg("--id")
            .arg(device_id.to_string())
            .output()
            .map_err(|e| MonitorError::InitializationFailed(
                format!("Failed to get device name: {}", e)
            ))?;
        
        let name = String::from_utf8_lossy(&name_output.stdout)
            .lines()
            .nth(1) // Skip header
            .unwrap_or("Unknown AMD GPU")
            .to_string();
        
        // Get memory info
        let memory_output = Command::new(rocm_smi_path)
            .arg("--showmeminfo")
            .arg("vram")
            .arg("--csv")
            .arg("--id")
            .arg(device_id.to_string())
            .output()
            .map_err(|e| MonitorError::InitializationFailed(
                format!("Failed to get memory info: {}", e)
            ))?;
        
        let memory_total = Self::parse_memory_total(&String::from_utf8_lossy(&memory_output.stdout))?;
        
        // Get clock info
        let clock_output = Command::new(rocm_smi_path)
            .arg("--showclocks")
            .arg("--csv")
            .arg("--id")
            .arg(device_id.to_string())
            .output()
            .map_err(|e| MonitorError::InitializationFailed(
                format!("Failed to get clock info: {}", e)
            ))?;
        
        let (max_clock, memory_clock) = Self::parse_clock_info(&String::from_utf8_lossy(&clock_output.stdout))?;
        
        // Detect architecture from name
        let architecture = Self::detect_amd_architecture(&name);
        
        Ok(AmdDeviceInfo {
            device_id,
            name,
            architecture,
            memory_total,
            memory_type: "GDDR6".to_string(), // Default, could be enhanced
            compute_units: Self::estimate_compute_units(&name),
            max_clock,
            memory_clock,
        })
    }
    
    fn get_capabilities(rocm_smi_path: &str) -> Result<AmdCapabilities, MonitorError> {
        // Check ECC support
        let ecc_output = Command::new(rocm_smi_path)
            .arg("--showmeminfo")
            .arg("ecc")
            .output();
        
        let supports_ecc = ecc_output.is_ok() && ecc_output.unwrap().status.success();
        
        // Check power management support
        let power_output = Command::new(rocm_smi_path)
            .arg("--showpower")
            .output();
        
        let supports_power_management = power_output.is_ok() && power_output.unwrap().status.success();
        
        // Check clock control support
        let clock_output = Command::new(rocm_smi_path)
            .arg("--showclocks")
            .output();
        
        let supports_clock_control = clock_output.is_ok() && clock_output.unwrap().status.success();
        
        // Check fan control support
        let fan_output = Command::new(rocm_smi_path)
            .arg("--showfan")
            .output();
        
        let supports_fan_control = fan_output.is_ok() && fan_output.unwrap().status.success();
        
        Ok(AmdCapabilities {
            supports_ecc,
            supports_power_management,
            supports_clock_control,
            supports_fan_control,
            max_power_limit: 300, // Default, could be enhanced
        })
    }
    
    fn parse_memory_total(output: &str) -> Result<u64, MonitorError> {
        // Parse memory total from ROCm SMI output
        // Format is typically: "vram,Total,<size_in_bytes>"
        for line in output.lines() {
            if line.contains("vram") && line.contains("Total") {
                let parts: Vec<&str> = line.split(',').collect();
                if parts.len() >= 3 {
                    if let Ok(bytes) = parts[2].parse::<u64>() {
                        return Ok(bytes / (1024 * 1024)); // Convert to MB
                    }
                }
            }
        }
        
        // Fallback to default if parsing fails
        Ok(8192) // 8GB default
    }
    
    fn parse_clock_info(output: &str) -> Result<(u32, u32), MonitorError> {
        let mut max_clock = 0u32;
        let mut memory_clock = 0u32;
        
        for line in output.lines() {
            if line.contains("gfx") && line.contains("mclk") {
                let parts: Vec<&str> = line.split(',').collect();
                if parts.len() >= 3 {
                    if let Ok(clock) = parts[2].parse::<u32>() {
                        if line.contains("gfx") {
                            max_clock = clock;
                        } else if line.contains("mclk") {
                            memory_clock = clock;
                        }
                    }
                }
            }
        }
        
        // Fallback values if parsing fails
        if max_clock == 0 { max_clock = 2000; }
        if memory_clock == 0 { memory_clock = 1000; }
        
        Ok((max_clock, memory_clock))
    }
    
    fn detect_amd_architecture(name: &str) -> String {
        let name_lower = name.to_lowercase();
        
        if name_lower.contains("rx 7900") || name_lower.contains("rx 7800") {
            "RDNA3".to_string()
        } else if name_lower.contains("rx 6800") || name_lower.contains("rx 6700") {
            "RDNA2".to_string()
        } else if name_lower.contains("rx 5700") || name_lower.contains("rx 5600") {
            "RDNA1".to_string()
        } else if name_lower.contains("rx 580") || name_lower.contains("rx 570") {
            "Polaris".to_string()
        } else if name_lower.contains("rx 480") || name_lower.contains("rx 470") {
            "Polaris".to_string()
        } else if name_lower.contains("r9") || name_lower.contains("r7") {
            "GCN".to_string()
        } else {
            "Unknown".to_string()
        }
    }
    
    fn estimate_compute_units(name: &str) -> u32 {
        let name_lower = name.to_lowercase();
        
        if name_lower.contains("rx 7900 xtx") {
            96
        } else if name_lower.contains("rx 7900 xt") {
            84
        } else if name_lower.contains("rx 7800 xt") {
            60
        } else if name_lower.contains("rx 6800 xt") {
            72
        } else if name_lower.contains("rx 6700 xt") {
            40
        } else if name_lower.contains("rx 5700 xt") {
            40
        } else if name_lower.contains("rx 580") {
            36
        } else if name_lower.contains("rx 570") {
            32
        } else {
            32 // Default estimate
        }
    }
}

impl GpuMonitor for AmdMonitor {
    fn detect_gpus(&self) -> Result<Vec<GpuInfo>, MonitorError> {
        let mut gpus = Vec::new();
        
        for (gpu_id, device_info) in &self.device_info {
            let gpu_info = GpuInfo {
                id: gpu_id.clone(),
                name: device_info.name.clone(),
                vendor: GpuVendor::AMD,
                architecture: device_info.architecture.clone(),
                memory_total: device_info.memory_total,
                capabilities: vec![
                    "compute".to_string(),
                    "graphics".to_string(),
                    if self.capabilities.supports_ecc { "ecc".to_string() } else { "".to_string() },
                    if self.capabilities.supports_power_management { "power_management".to_string() } else { "".to_string() },
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
        
        // Get utilization
        let utilization_output = Command::new(&self.rocm_smi_path)
            .arg("--showuse")
            .arg("--csv")
            .arg("--id")
            .arg(device_id.to_string())
            .output()
            .map_err(|e| MonitorError::TelemetryCollectionFailed(
                format!("Failed to get utilization: {}", e)
            ))?;
        
        let (gpu_util, memory_util) = Self::parse_utilization(&String::from_utf8_lossy(&utilization_output.stdout))?;
        
        // Get memory usage
        let memory_output = Command::new(&self.rocm_smi_path)
            .arg("--showmemuse")
            .arg("--csv")
            .arg("--id")
            .arg(device_id.to_string())
            .output()
            .map_err(|e| MonitorError::TelemetryCollectionFailed(
                format!("Failed to get memory usage: {}", e)
            ))?;
        
        let memory_used = Self::parse_memory_used(&String::from_utf8_lossy(&memory_output.stdout))?;
        
        // Get temperature
        let temp_output = Command::new(&self.rocm_smi_path)
            .arg("--showtemp")
            .arg("--csv")
            .arg("--id")
            .arg(device_id.to_string())
            .output()
            .map_err(|e| MonitorError::TelemetryCollectionFailed(
                format!("Failed to get temperature: {}", e)
            ))?;
        
        let temperature = Self::parse_temperature(&String::from_utf8_lossy(&temp_output.stdout))?;
        
        // Get power draw
        let power_output = Command::new(&self.rocm_smi_path)
            .arg("--showpower")
            .arg("--csv")
            .arg("--id")
            .arg(device_id.to_string())
            .output()
            .map_err(|e| MonitorError::TelemetryCollectionFailed(
                format!("Failed to get power draw: {}", e)
            ))?;
        
        let power_draw = Self::parse_power_draw(&String::from_utf8_lossy(&power_output.stdout))?;
        
        // Get current clocks
        let clock_output = Command::new(&self.rocm_smi_path)
            .arg("--showclocks")
            .arg("--csv")
            .arg("--id")
            .arg(device_id.to_string())
            .output()
            .map_err(|e| MonitorError::TelemetryCollectionFailed(
                format!("Failed to get clock info: {}", e)
            ))?;
        
        let (current_gpu_clock, current_memory_clock) = Self::parse_clock_info(&String::from_utf8_lossy(&clock_output.stdout))?;
        
        // Get ECC errors if supported
        let (ecc_correctable, ecc_uncorrectable) = if self.capabilities.supports_ecc {
            Self::get_ecc_errors(&self.rocm_smi_path, device_id).unwrap_or((0, 0))
        } else {
            (0, 0)
        };
        
        Ok(GpuMetrics {
            gpu_id: gpu_id.to_string(),
            gpu_name: device_info.name.clone(),
            utilization_gpu: gpu_util,
            utilization_memory: memory_util,
            utilization_encoder: None, // ROCm SMI doesn't provide encoder/decoder utilization
            utilization_decoder: None,
            memory_used,
            memory_total: device_info.memory_total,
            temperature,
            power_draw,
            clock_gpu: current_gpu_clock,
            clock_memory: current_memory_clock,
            throttling_reasons: "".to_string(), // ROCm SMI doesn't provide throttling reasons
            performance_state: "Unknown".to_string(), // ROCm SMI doesn't provide performance state
            pcie_tx_throughput_mbps: None, // Not available in ROCm SMI
            pcie_rx_throughput_mbps: None,
            ecc_errors_correctable: Some(ecc_correctable),
            ecc_errors_uncorrectable: Some(ecc_uncorrectable),
            vendor: GpuVendor::AMD,
            architecture: device_info.architecture.clone(),
        })
    }
    
    fn monitor_name(&self) -> &'static str {
        "AMD ROCm SMI Monitor"
    }
    
    fn is_available(&self) -> bool {
        self.device_count > 0
    }
}

impl AmdMonitor {
    fn parse_utilization(output: &str) -> Result<(u32, u32), MonitorError> {
        let mut gpu_util = 0u32;
        let mut memory_util = 0u32;
        
        for line in output.lines() {
            if line.contains("gfx") && line.contains("use") {
                let parts: Vec<&str> = line.split(',').collect();
                if parts.len() >= 3 {
                    if let Ok(util) = parts[2].parse::<u32>() {
                        gpu_util = util;
                    }
                }
            } else if line.contains("mem") && line.contains("use") {
                let parts: Vec<&str> = line.split(',').collect();
                if parts.len() >= 3 {
                    if let Ok(util) = parts[2].parse::<u32>() {
                        memory_util = util;
                    }
                }
            }
        }
        
        Ok((gpu_util, memory_util))
    }
    
    fn parse_memory_used(output: &str) -> Result<u64, MonitorError> {
        for line in output.lines() {
            if line.contains("vram") && line.contains("Used") {
                let parts: Vec<&str> = line.split(',').collect();
                if parts.len() >= 3 {
                    if let Ok(bytes) = parts[2].parse::<u64>() {
                        return Ok(bytes / (1024 * 1024)); // Convert to MB
                    }
                }
            }
        }
        
        Ok(0) // Default if parsing fails
    }
    
    fn parse_temperature(output: &str) -> Result<u32, MonitorError> {
        for line in output.lines() {
            if line.contains("temp") && line.contains("edge") {
                let parts: Vec<&str> = line.split(',').collect();
                if parts.len() >= 3 {
                    if let Ok(temp) = parts[2].parse::<u32>() {
                        return Ok(temp);
                    }
                }
            }
        }
        
        Ok(50) // Default temperature if parsing fails
    }
    
    fn parse_power_draw(output: &str) -> Result<u32, MonitorError> {
        for line in output.lines() {
            if line.contains("power") && line.contains("draw") {
                let parts: Vec<&str> = line.split(',').collect();
                if parts.len() >= 3 {
                    if let Ok(power) = parts[2].parse::<u32>() {
                        return Ok(power);
                    }
                }
            }
        }
        
        Ok(100) // Default power draw if parsing fails
    }
    
    fn get_ecc_errors(rocm_smi_path: &str, device_id: u32) -> Result<(u32, u32), MonitorError> {
        let output = Command::new(rocm_smi_path)
            .arg("--showmeminfo")
            .arg("ecc")
            .arg("--csv")
            .arg("--id")
            .arg(device_id.to_string())
            .output()
            .map_err(|e| MonitorError::TelemetryCollectionFailed(
                format!("Failed to get ECC errors: {}", e)
            ))?;
        
        let mut correctable = 0u32;
        let mut uncorrectable = 0u32;
        
        for line in String::from_utf8_lossy(&output.stdout).lines() {
            if line.contains("correctable") {
                let parts: Vec<&str> = line.split(',').collect();
                if parts.len() >= 3 {
                    if let Ok(errors) = parts[2].parse::<u32>() {
                        correctable = errors;
                    }
                }
            } else if line.contains("uncorrectable") {
                let parts: Vec<&str> = line.split(',').collect();
                if parts.len() >= 3 {
                    if let Ok(errors) = parts[2].parse::<u32>() {
                        uncorrectable = errors;
                    }
                }
            }
        }
        
        Ok((correctable, uncorrectable))
    }
} 