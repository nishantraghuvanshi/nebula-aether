// apps/agent/src/monitor/anomaly.rs
// Advanced anomaly detection system for GPU telemetry
//
// This module provides real-time anomaly detection capabilities including
// statistical analysis, pattern recognition, and ML-based detection.

use crate::monitor::{GpuMetrics, MonitorError};
use std::collections::VecDeque;
use std::time::{SystemTime, UNIX_EPOCH};
use serde::{Serialize, Deserialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnomalyEvent {
    pub gpu_id: String,
    pub anomaly_type: AnomalyType,
    pub severity: Severity,
    pub timestamp: SystemTime,
    pub value: f64,
    pub threshold: f64,
    pub description: String,
    pub confidence: f64,
    pub metadata: std::collections::HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AnomalyType {
    HighTemperature,
    HighPowerDraw,
    UnusualUtilization,
    MemoryLeak,
    ClockAnomaly,
    EccErrors,
    PerformanceDegradation,
    ThermalThrottling,
    PowerThrottling,
    MemoryBandwidthAnomaly,
    Custom(String),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Severity {
    Info,
    Warning,
    Critical,
    Emergency,
}

#[derive(Debug, Clone)]
pub struct AnomalyDetector {
    // Configuration
    temperature_threshold: u32,
    power_threshold: u32,
    utilization_threshold: (u32, u32), // (min, max)
    memory_leak_threshold: f64,
    clock_anomaly_threshold: f64,
    ecc_error_threshold: u32,
    
    // History for pattern analysis
    anomaly_history: VecDeque<AnomalyEvent>,
    metrics_history: VecDeque<GpuMetrics>,
    max_history_size: usize,
    
    // Statistical analysis
    baseline_metrics: Option<BaselineMetrics>,
    baseline_established: bool,
    
    // Pattern detection
    pattern_detector: PatternDetector,
    
    // Alert system
    alert_cooldown: std::collections::HashMap<String, SystemTime>,
    alert_cooldown_duration: std::time::Duration,
}

#[derive(Debug, Clone)]
struct BaselineMetrics {
    avg_temperature: f64,
    avg_power_draw: f64,
    avg_utilization: f64,
    avg_memory_usage: f64,
    avg_clock_gpu: f64,
    avg_clock_memory: f64,
    std_temperature: f64,
    std_power_draw: f64,
    std_utilization: f64,
    std_memory_usage: f64,
    std_clock_gpu: f64,
    std_clock_memory: f64,
}

#[derive(Debug, Clone)]
struct PatternDetector {
    utilization_patterns: VecDeque<f64>,
    temperature_patterns: VecDeque<f64>,
    power_patterns: VecDeque<f64>,
    pattern_window_size: usize,
}

impl AnomalyDetector {
    pub fn new() -> Self {
        Self {
            temperature_threshold: 85,
            power_threshold: 300,
            utilization_threshold: (5, 95),
            memory_leak_threshold: 0.1, // 10% increase per minute
            clock_anomaly_threshold: 0.2, // 20% deviation
            ecc_error_threshold: 1,
            
            anomaly_history: VecDeque::new(),
            metrics_history: VecDeque::new(),
            max_history_size: 1000,
            
            baseline_metrics: None,
            baseline_established: false,
            
            pattern_detector: PatternDetector {
                utilization_patterns: VecDeque::new(),
                temperature_patterns: VecDeque::new(),
                power_patterns: VecDeque::new(),
                pattern_window_size: 50,
            },
            
            alert_cooldown: std::collections::HashMap::new(),
            alert_cooldown_duration: std::time::Duration::from_secs(300), // 5 minutes
        }
    }
    
    pub fn detect_anomalies(&mut self, metrics: &GpuMetrics) -> Vec<AnomalyEvent> {
        let mut anomalies = Vec::new();
        
        // Add metrics to history
        self.add_metrics_to_history(metrics);
        
        // Establish baseline if not done yet
        if !self.baseline_established && self.metrics_history.len() >= 100 {
            self.establish_baseline();
        }
        
        // Detect various types of anomalies
        anomalies.extend(self.detect_temperature_anomaly(metrics));
        anomalies.extend(self.detect_power_anomaly(metrics));
        anomalies.extend(self.detect_utilization_anomaly(metrics));
        anomalies.extend(self.detect_memory_leak(metrics));
        anomalies.extend(self.detect_clock_anomaly(metrics));
        anomalies.extend(self.detect_ecc_anomaly(metrics));
        anomalies.extend(self.detect_performance_degradation(metrics));
        anomalies.extend(self.detect_thermal_throttling(metrics));
        anomalies.extend(self.detect_power_throttling(metrics));
        anomalies.extend(self.detect_memory_bandwidth_anomaly(metrics));
        
        // Pattern-based anomaly detection
        anomalies.extend(self.detect_pattern_anomalies(metrics));
        
        // Statistical anomaly detection
        if self.baseline_established {
            anomalies.extend(self.detect_statistical_anomalies(metrics));
        }
        
        // Store anomalies in history
        for anomaly in &anomalies {
            self.anomaly_history.push_back(anomaly.clone());
        }
        
        // Maintain history size
        while self.anomaly_history.len() > self.max_history_size {
            self.anomaly_history.pop_front();
        }
        
        anomalies
    }
    
    fn add_metrics_to_history(&mut self, metrics: &GpuMetrics) {
        self.metrics_history.push_back(metrics.clone());
        while self.metrics_history.len() > self.max_history_size {
            self.metrics_history.pop_front();
        }
        
        // Add to pattern detectors
        self.pattern_detector.utilization_patterns.push_back(metrics.utilization_gpu as f64);
        self.pattern_detector.temperature_patterns.push_back(metrics.temperature as f64);
        self.pattern_detector.power_patterns.push_back(metrics.power_draw as f64);
        
        while self.pattern_detector.utilization_patterns.len() > self.pattern_detector.pattern_window_size {
            self.pattern_detector.utilization_patterns.pop_front();
        }
        while self.pattern_detector.temperature_patterns.len() > self.pattern_detector.pattern_window_size {
            self.pattern_detector.temperature_patterns.pop_front();
        }
        while self.pattern_detector.power_patterns.len() > self.pattern_detector.pattern_window_size {
            self.pattern_detector.power_patterns.pop_front();
        }
    }
    
    fn establish_baseline(&mut self) {
        if self.metrics_history.len() < 100 {
            return;
        }
        
        let recent_metrics: Vec<&GpuMetrics> = self.metrics_history.iter().rev().take(100).collect();
        
        let avg_temperature = recent_metrics.iter().map(|m| m.temperature as f64).sum::<f64>() / recent_metrics.len() as f64;
        let avg_power_draw = recent_metrics.iter().map(|m| m.power_draw as f64).sum::<f64>() / recent_metrics.len() as f64;
        let avg_utilization = recent_metrics.iter().map(|m| m.utilization_gpu as f64).sum::<f64>() / recent_metrics.len() as f64;
        let avg_memory_usage = recent_metrics.iter().map(|m| m.memory_used as f64).sum::<f64>() / recent_metrics.len() as f64;
        let avg_clock_gpu = recent_metrics.iter().map(|m| m.clock_gpu as f64).sum::<f64>() / recent_metrics.len() as f64;
        let avg_clock_memory = recent_metrics.iter().map(|m| m.clock_memory as f64).sum::<f64>() / recent_metrics.len() as f64;
        
        // Calculate standard deviations
        let std_temperature = Self::calculate_std_dev(recent_metrics.iter().map(|m| m.temperature as f64), avg_temperature);
        let std_power_draw = Self::calculate_std_dev(recent_metrics.iter().map(|m| m.power_draw as f64), avg_power_draw);
        let std_utilization = Self::calculate_std_dev(recent_metrics.iter().map(|m| m.utilization_gpu as f64), avg_utilization);
        let std_memory_usage = Self::calculate_std_dev(recent_metrics.iter().map(|m| m.memory_used as f64), avg_memory_usage);
        let std_clock_gpu = Self::calculate_std_dev(recent_metrics.iter().map(|m| m.clock_gpu as f64), avg_clock_gpu);
        let std_clock_memory = Self::calculate_std_dev(recent_metrics.iter().map(|m| m.clock_memory as f64), avg_clock_memory);
        
        self.baseline_metrics = Some(BaselineMetrics {
            avg_temperature,
            avg_power_draw,
            avg_utilization,
            avg_memory_usage,
            avg_clock_gpu,
            avg_clock_memory,
            std_temperature,
            std_power_draw,
            std_utilization,
            std_memory_usage,
            std_clock_gpu,
            std_clock_memory,
        });
        
        self.baseline_established = true;
    }
    
    fn calculate_std_dev<I>(values: I, mean: f64) -> f64 
    where 
        I: Iterator<Item = f64>,
    {
        let values_vec: Vec<f64> = values.collect();
        if values_vec.is_empty() {
            return 0.0;
        }
        
        let variance = values_vec.iter()
            .map(|&x| (x - mean).powi(2))
            .sum::<f64>() / values_vec.len() as f64;
        
        variance.sqrt()
    }
    
    fn detect_temperature_anomaly(&self, metrics: &GpuMetrics) -> Vec<AnomalyEvent> {
        let mut anomalies = Vec::new();
        
        if metrics.temperature > self.temperature_threshold {
            let severity = if metrics.temperature > 95 {
                Severity::Emergency
            } else if metrics.temperature > 90 {
                Severity::Critical
            } else {
                Severity::Warning
            };
            
            anomalies.push(AnomalyEvent {
                gpu_id: metrics.gpu_id.clone(),
                anomaly_type: AnomalyType::HighTemperature,
                severity,
                timestamp: SystemTime::now(),
                value: metrics.temperature as f64,
                threshold: self.temperature_threshold as f64,
                description: format!("GPU temperature {}°C exceeds threshold {}°C", 
                    metrics.temperature, self.temperature_threshold),
                confidence: self.calculate_confidence(metrics.temperature as f64, self.temperature_threshold as f64),
                metadata: std::collections::HashMap::new(),
            });
        }
        
        anomalies
    }
    
    fn detect_power_anomaly(&self, metrics: &GpuMetrics) -> Vec<AnomalyEvent> {
        let mut anomalies = Vec::new();
        
        if metrics.power_draw > self.power_threshold {
            let severity = if metrics.power_draw > self.power_threshold * 2 {
                Severity::Emergency
            } else if metrics.power_draw > self.power_threshold * 3 / 2 {
                Severity::Critical
            } else {
                Severity::Warning
            };
            
            anomalies.push(AnomalyEvent {
                gpu_id: metrics.gpu_id.clone(),
                anomaly_type: AnomalyType::HighPowerDraw,
                severity,
                timestamp: SystemTime::now(),
                value: metrics.power_draw as f64,
                threshold: self.power_threshold as f64,
                description: format!("GPU power draw {}W exceeds threshold {}W", 
                    metrics.power_draw, self.power_threshold),
                confidence: self.calculate_confidence(metrics.power_draw as f64, self.power_threshold as f64),
                metadata: std::collections::HashMap::new(),
            });
        }
        
        anomalies
    }
    
    fn detect_utilization_anomaly(&self, metrics: &GpuMetrics) -> Vec<AnomalyEvent> {
        let mut anomalies = Vec::new();
        
        if metrics.utilization_gpu < self.utilization_threshold.0 || 
           metrics.utilization_gpu > self.utilization_threshold.1 {
            
            let severity = if metrics.utilization_gpu == 0 || metrics.utilization_gpu == 100 {
                Severity::Warning
            } else {
                Severity::Info
            };
            
            anomalies.push(AnomalyEvent {
                gpu_id: metrics.gpu_id.clone(),
                anomaly_type: AnomalyType::UnusualUtilization,
                severity,
                timestamp: SystemTime::now(),
                value: metrics.utilization_gpu as f64,
                threshold: if metrics.utilization_gpu < self.utilization_threshold.0 {
                    self.utilization_threshold.0 as f64
                } else {
                    self.utilization_threshold.1 as f64
                },
                description: format!("GPU utilization {}% is outside normal range {}-{}%", 
                    metrics.utilization_gpu, self.utilization_threshold.0, self.utilization_threshold.1),
                confidence: 0.8,
                metadata: std::collections::HashMap::new(),
            });
        }
        
        anomalies
    }
    
    fn detect_memory_leak(&self, metrics: &GpuMetrics) -> Vec<AnomalyEvent> {
        let mut anomalies = Vec::new();
        
        if self.metrics_history.len() >= 10 {
            let recent_memory: Vec<u64> = self.metrics_history.iter()
                .rev()
                .take(10)
                .map(|m| m.memory_used)
                .collect();
            
            if recent_memory.len() >= 5 {
                let memory_trend = self.calculate_trend(&recent_memory);
                if memory_trend > self.memory_leak_threshold {
                    anomalies.push(AnomalyEvent {
                        gpu_id: metrics.gpu_id.clone(),
                        anomaly_type: AnomalyType::MemoryLeak,
                        severity: Severity::Warning,
                        timestamp: SystemTime::now(),
                        value: memory_trend,
                        threshold: self.memory_leak_threshold,
                        description: format!("Potential memory leak detected: {}% increase per minute", 
                            memory_trend * 100.0),
                        confidence: 0.7,
                        metadata: std::collections::HashMap::new(),
                    });
                }
            }
        }
        
        anomalies
    }
    
    fn detect_clock_anomaly(&self, metrics: &GpuMetrics) -> Vec<AnomalyEvent> {
        let mut anomalies = Vec::new();
        
        if let Some(baseline) = &self.baseline_metrics {
            let clock_deviation = (metrics.clock_gpu as f64 - baseline.avg_clock_gpu).abs() / baseline.avg_clock_gpu;
            
            if clock_deviation > self.clock_anomaly_threshold {
                anomalies.push(AnomalyEvent {
                    gpu_id: metrics.gpu_id.clone(),
                    anomaly_type: AnomalyType::ClockAnomaly,
                    severity: Severity::Warning,
                    timestamp: SystemTime::now(),
                    value: clock_deviation,
                    threshold: self.clock_anomaly_threshold,
                    description: format!("GPU clock {}MHz deviates {}% from baseline {}MHz", 
                        metrics.clock_gpu, clock_deviation * 100.0, baseline.avg_clock_gpu as u32),
                    confidence: 0.8,
                    metadata: std::collections::HashMap::new(),
                });
            }
        }
        
        anomalies
    }
    
    fn detect_ecc_anomaly(&self, metrics: &GpuMetrics) -> Vec<AnomalyEvent> {
        let mut anomalies = Vec::new();
        
        if let Some(ecc_errors) = metrics.ecc_errors_uncorrectable {
            if ecc_errors > self.ecc_error_threshold {
                anomalies.push(AnomalyEvent {
                    gpu_id: metrics.gpu_id.clone(),
                    anomaly_type: AnomalyType::EccErrors,
                    severity: Severity::Critical,
                    timestamp: SystemTime::now(),
                    value: ecc_errors as f64,
                    threshold: self.ecc_error_threshold as f64,
                    description: format!("Uncorrectable ECC errors detected: {}", ecc_errors),
                    confidence: 1.0,
                    metadata: std::collections::HashMap::new(),
                });
            }
        }
        
        anomalies
    }
    
    fn detect_performance_degradation(&self, metrics: &GpuMetrics) -> Vec<AnomalyEvent> {
        let mut anomalies = Vec::new();
        
        if let Some(baseline) = &self.baseline_metrics {
            if self.metrics_history.len() >= 20 {
                let recent_performance: Vec<f64> = self.metrics_history.iter()
                    .rev()
                    .take(20)
                    .map(|m| m.utilization_gpu as f64)
                    .collect();
                
                let avg_recent_performance = recent_performance.iter().sum::<f64>() / recent_performance.len() as f64;
                let performance_degradation = (baseline.avg_utilization - avg_recent_performance) / baseline.avg_utilization;
                
                if performance_degradation > 0.3 { // 30% degradation
                    anomalies.push(AnomalyEvent {
                        gpu_id: metrics.gpu_id.clone(),
                        anomaly_type: AnomalyType::PerformanceDegradation,
                        severity: Severity::Warning,
                        timestamp: SystemTime::now(),
                        value: performance_degradation,
                        threshold: 0.3,
                        description: format!("Performance degradation detected: {}% below baseline", 
                            performance_degradation * 100.0),
                        confidence: 0.8,
                        metadata: std::collections::HashMap::new(),
                    });
                }
            }
        }
        
        anomalies
    }
    
    fn detect_thermal_throttling(&self, metrics: &GpuMetrics) -> Vec<AnomalyEvent> {
        let mut anomalies = Vec::new();
        
        // Check if performance state indicates thermal throttling
        if metrics.temperature > 80 && metrics.utilization_gpu < 50 {
            anomalies.push(AnomalyEvent {
                gpu_id: metrics.gpu_id.clone(),
                anomaly_type: AnomalyType::ThermalThrottling,
                severity: Severity::Warning,
                timestamp: SystemTime::now(),
                value: metrics.temperature as f64,
                threshold: 80.0,
                description: format!("Thermal throttling suspected: high temp {}°C with low utilization {}%", 
                    metrics.temperature, metrics.utilization_gpu),
                confidence: 0.7,
                metadata: std::collections::HashMap::new(),
            });
        }
        
        anomalies
    }
    
    fn detect_power_throttling(&self, metrics: &GpuMetrics) -> Vec<AnomalyEvent> {
        let mut anomalies = Vec::new();
        
        // Check if power draw is high but utilization is low (power throttling)
        if metrics.power_draw > 200 && metrics.utilization_gpu < 30 {
            anomalies.push(AnomalyEvent {
                gpu_id: metrics.gpu_id.clone(),
                anomaly_type: AnomalyType::PowerThrottling,
                severity: Severity::Warning,
                timestamp: SystemTime::now(),
                value: metrics.power_draw as f64,
                threshold: 200.0,
                description: format!("Power throttling suspected: high power {}W with low utilization {}%", 
                    metrics.power_draw, metrics.utilization_gpu),
                confidence: 0.6,
                metadata: std::collections::HashMap::new(),
            });
        }
        
        anomalies
    }
    
    fn detect_memory_bandwidth_anomaly(&self, metrics: &GpuMetrics) -> Vec<AnomalyEvent> {
        let mut anomalies = Vec::new();
        
        // Check for unusual memory utilization patterns
        if metrics.utilization_memory > 90 && metrics.utilization_gpu < 20 {
            anomalies.push(AnomalyEvent {
                gpu_id: metrics.gpu_id.clone(),
                anomaly_type: AnomalyType::MemoryBandwidthAnomaly,
                severity: Severity::Warning,
                timestamp: SystemTime::now(),
                value: metrics.utilization_memory as f64,
                threshold: 90.0,
                description: format!("Memory bandwidth anomaly: high memory utilization {}% with low GPU utilization {}%", 
                    metrics.utilization_memory, metrics.utilization_gpu),
                confidence: 0.7,
                metadata: std::collections::HashMap::new(),
            });
        }
        
        anomalies
    }
    
    fn detect_pattern_anomalies(&self, metrics: &GpuMetrics) -> Vec<AnomalyEvent> {
        let mut anomalies = Vec::new();
        
        // Detect sudden spikes or drops in utilization
        if self.pattern_detector.utilization_patterns.len() >= 5 {
            let recent_util: Vec<f64> = self.pattern_detector.utilization_patterns.iter()
                .rev()
                .take(5)
                .cloned()
                .collect();
            
            let utilization_variance = self.calculate_variance(&recent_util);
            if utilization_variance > 1000.0 { // High variance indicates instability
                anomalies.push(AnomalyEvent {
                    gpu_id: metrics.gpu_id.clone(),
                    anomaly_type: AnomalyType::UnusualUtilization,
                    severity: Severity::Info,
                    timestamp: SystemTime::now(),
                    value: utilization_variance,
                    threshold: 1000.0,
                    description: format!("Unstable utilization pattern detected: variance {}", utilization_variance),
                    confidence: 0.6,
                    metadata: std::collections::HashMap::new(),
                });
            }
        }
        
        anomalies
    }
    
    fn detect_statistical_anomalies(&self, metrics: &GpuMetrics) -> Vec<AnomalyEvent> {
        let mut anomalies = Vec::new();
        
        if let Some(baseline) = &self.baseline_metrics {
            // Z-score based anomaly detection
            let temp_z_score = (metrics.temperature as f64 - baseline.avg_temperature) / baseline.std_temperature;
            let power_z_score = (metrics.power_draw as f64 - baseline.avg_power_draw) / baseline.std_power_draw;
            let util_z_score = (metrics.utilization_gpu as f64 - baseline.avg_utilization) / baseline.std_utilization;
            
            // Flag anomalies with Z-score > 3 (3 standard deviations)
            if temp_z_score.abs() > 3.0 {
                anomalies.push(AnomalyEvent {
                    gpu_id: metrics.gpu_id.clone(),
                    anomaly_type: AnomalyType::HighTemperature,
                    severity: if temp_z_score > 3.0 { Severity::Critical } else { Severity::Warning },
                    timestamp: SystemTime::now(),
                    value: temp_z_score,
                    threshold: 3.0,
                    description: format!("Statistical temperature anomaly: Z-score {}", temp_z_score),
                    confidence: 0.9,
                    metadata: std::collections::HashMap::new(),
                });
            }
            
            if power_z_score.abs() > 3.0 {
                anomalies.push(AnomalyEvent {
                    gpu_id: metrics.gpu_id.clone(),
                    anomaly_type: AnomalyType::HighPowerDraw,
                    severity: if power_z_score > 3.0 { Severity::Critical } else { Severity::Warning },
                    timestamp: SystemTime::now(),
                    value: power_z_score,
                    threshold: 3.0,
                    description: format!("Statistical power anomaly: Z-score {}", power_z_score),
                    confidence: 0.9,
                    metadata: std::collections::HashMap::new(),
                });
            }
            
            if util_z_score.abs() > 3.0 {
                anomalies.push(AnomalyEvent {
                    gpu_id: metrics.gpu_id.clone(),
                    anomaly_type: AnomalyType::UnusualUtilization,
                    severity: Severity::Info,
                    timestamp: SystemTime::now(),
                    value: util_z_score,
                    threshold: 3.0,
                    description: format!("Statistical utilization anomaly: Z-score {}", util_z_score),
                    confidence: 0.8,
                    metadata: std::collections::HashMap::new(),
                });
            }
        }
        
        anomalies
    }
    
    fn calculate_trend(&self, values: &[u64]) -> f64 {
        if values.len() < 2 {
            return 0.0;
        }
        
        let first = values[0] as f64;
        let last = values[values.len() - 1] as f64;
        
        (last - first) / first
    }
    
    fn calculate_variance(&self, values: &[f64]) -> f64 {
        if values.is_empty() {
            return 0.0;
        }
        
        let mean = values.iter().sum::<f64>() / values.len() as f64;
        let variance = values.iter()
            .map(|&x| (x - mean).powi(2))
            .sum::<f64>() / values.len() as f64;
        
        variance
    }
    
    fn calculate_confidence(&self, value: f64, threshold: f64) -> f64 {
        let deviation = (value - threshold).abs() / threshold;
        (deviation * 0.5).min(1.0)
    }
    
    pub fn get_anomaly_history(&self) -> &VecDeque<AnomalyEvent> {
        &self.anomaly_history
    }
    
    pub fn get_baseline_metrics(&self) -> Option<&BaselineMetrics> {
        self.baseline_metrics.as_ref()
    }
    
    pub fn is_baseline_established(&self) -> bool {
        self.baseline_established
    }
    
    pub fn should_alert(&mut self, anomaly: &AnomalyEvent) -> bool {
        let alert_key = format!("{}_{:?}", anomaly.gpu_id, anomaly.anomaly_type);
        let now = SystemTime::now();
        
        if let Some(last_alert) = self.alert_cooldown.get(&alert_key) {
            if now.duration_since(*last_alert).unwrap_or_default() < self.alert_cooldown_duration {
                return false;
            }
        }
        
        self.alert_cooldown.insert(alert_key, now);
        true
    }
}
