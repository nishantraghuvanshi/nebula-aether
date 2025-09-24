// apps/agent/src/monitor/health.rs
// Advanced health monitoring and predictive maintenance system for GPUs
//
// This module provides comprehensive health monitoring capabilities including
// health scoring, predictive maintenance, and maintenance scheduling.

use crate::monitor::{GpuMetrics, MonitorError, GpuVendor};
use std::collections::{HashMap, VecDeque};
use std::time::{SystemTime, Duration};
use serde::{Serialize, Deserialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthAssessment {
    pub gpu_id: String,
    pub health_score: f64,
    pub health_status: HealthStatus,
    pub maintenance_needed: bool,
    pub next_maintenance: Option<SystemTime>,
    pub recommendations: Vec<HealthRecommendation>,
    pub risk_factors: Vec<RiskFactor>,
    pub timestamp: SystemTime,
    pub vendor: GpuVendor,
    pub architecture: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HealthStatus {
    Excellent,    // 90-100
    Good,         // 80-89
    Fair,         // 70-79
    Poor,         // 60-69
    Critical,     // 50-59
    Emergency,    // 0-49
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthRecommendation {
    pub title: String,
    pub description: String,
    pub priority: RecommendationPriority,
    pub action: HealthAction,
    pub expected_benefit: f64,
    pub urgency: Urgency,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum RecommendationPriority {
    Low,
    Medium,
    High,
    Critical,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HealthAction {
    CleanCoolingSystem,
    ReplaceThermalPaste,
    UpdateDrivers,
    CheckPowerConnections,
    MonitorTemperature,
    ScheduleMaintenance,
    ReplaceHardware,
    Custom(String),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Urgency {
    Low,      // Can wait weeks/months
    Medium,   // Should be done within days/weeks
    High,     // Should be done within hours/days
    Critical, // Should be done immediately
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskFactor {
    pub factor_type: RiskFactorType,
    pub severity: f64,
    pub description: String,
    pub mitigation: String,
    pub confidence: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum RiskFactorType {
    TemperatureRisk,
    PowerRisk,
    MemoryRisk,
    ClockRisk,
    EccRisk,
    UtilizationRisk,
    AgeRisk,
    WearRisk,
}

#[derive(Debug, Clone)]
pub struct HealthMonitor {
    health_history: HashMap<String, VecDeque<HealthMetric>>,
    health_scores: HashMap<String, f64>,
    maintenance_schedule: HashMap<String, MaintenanceSchedule>,
    predictive_models: HashMap<String, PredictiveModel>,
    health_thresholds: HealthThresholds,
}

#[derive(Debug, Clone)]
struct HealthMetric {
    pub gpu_id: String,
    pub timestamp: SystemTime,
    pub temperature_score: f64,
    pub power_score: f64,
    pub utilization_score: f64,
    pub memory_score: f64,
    pub ecc_score: f64,
    pub overall_health: f64,
    pub metrics: GpuMetrics,
}

#[derive(Debug, Clone)]
struct MaintenanceSchedule {
    pub gpu_id: String,
    pub last_maintenance: Option<SystemTime>,
    pub next_scheduled: Option<SystemTime>,
    pub maintenance_interval: Duration,
    pub maintenance_type: MaintenanceType,
    pub maintenance_history: Vec<MaintenanceRecord>,
}

#[derive(Debug, Clone)]
enum MaintenanceType {
    Preventive,
    Corrective,
    Predictive,
    Emergency,
}

#[derive(Debug, Clone)]
struct MaintenanceRecord {
    pub timestamp: SystemTime,
    pub maintenance_type: MaintenanceType,
    pub description: String,
    pub performed_by: String,
    pub health_improvement: f64,
}

#[derive(Debug, Clone)]
struct PredictiveModel {
    pub gpu_id: String,
    pub model_type: ModelType,
    pub accuracy: f64,
    pub last_trained: SystemTime,
    pub predictions: Vec<HealthPrediction>,
}

#[derive(Debug, Clone)]
enum ModelType {
    TemperatureTrend,
    PowerEfficiency,
    PerformanceDegradation,
    FailurePrediction,
}

#[derive(Debug, Clone)]
struct HealthPrediction {
    pub prediction_type: ModelType,
    pub predicted_value: f64,
    pub confidence: f64,
    pub prediction_horizon: Duration,
    pub timestamp: SystemTime,
}

#[derive(Debug, Clone)]
struct HealthThresholds {
    pub temperature_warning: u32,
    pub temperature_critical: u32,
    pub power_warning: u32,
    pub power_critical: u32,
    pub utilization_warning: (u32, u32),
    pub memory_warning: f64,
    pub ecc_warning: u32,
    pub age_warning_months: u32,
}

impl HealthMonitor {
    pub fn new() -> Self {
        Self {
            health_history: HashMap::new(),
            health_scores: HashMap::new(),
            maintenance_schedule: HashMap::new(),
            predictive_models: HashMap::new(),
            health_thresholds: HealthThresholds {
                temperature_warning: 80,
                temperature_critical: 90,
                power_warning: 250,
                power_critical: 300,
                utilization_warning: (5, 95),
                memory_warning: 0.9,
                ecc_warning: 1,
                age_warning_months: 24,
            },
        }
    }
    
    pub fn assess_health(&mut self, metrics: &GpuMetrics) -> HealthAssessment {
        let gpu_id = &metrics.gpu_id;
        
        // Calculate individual health scores
        let temperature_score = self.calculate_temperature_score(metrics);
        let power_score = self.calculate_power_score(metrics);
        let utilization_score = self.calculate_utilization_score(metrics);
        let memory_score = self.calculate_memory_score(metrics);
        let ecc_score = self.calculate_ecc_score(metrics);
        
        // Calculate overall health score
        let overall_health = (temperature_score + power_score + utilization_score + memory_score + ecc_score) / 5.0;
        
        // Create health metric record
        let health_metric = HealthMetric {
            gpu_id: gpu_id.clone(),
            timestamp: SystemTime::now(),
            temperature_score,
            power_score,
            utilization_score,
            memory_score,
            ecc_score,
            overall_health,
            metrics: metrics.clone(),
        };
        
        // Store in history
        self.health_history.entry(gpu_id.clone())
            .or_insert_with(VecDeque::new)
            .push_back(health_metric.clone());
        
        // Update health score
        self.health_scores.insert(gpu_id.clone(), overall_health);
        
        // Generate recommendations
        let recommendations = self.generate_health_recommendations(gpu_id, &health_metric);
        
        // Identify risk factors
        let risk_factors = self.identify_risk_factors(gpu_id, &health_metric);
        
        // Check if maintenance is needed
        let maintenance_needed = self.check_maintenance_needed(gpu_id, &health_metric);
        
        // Calculate next maintenance
        let next_maintenance = self.calculate_next_maintenance(gpu_id);
        
        // Update predictive models
        self.update_predictive_models(gpu_id, &health_metric);
        
        HealthAssessment {
            gpu_id: gpu_id.clone(),
            health_score: overall_health,
            health_status: self.determine_health_status(overall_health),
            maintenance_needed,
            next_maintenance,
            recommendations,
            risk_factors,
            timestamp: SystemTime::now(),
            vendor: metrics.vendor.clone(),
            architecture: metrics.architecture.clone(),
        }
    }
    
    fn calculate_temperature_score(&self, metrics: &GpuMetrics) -> f64 {
        let temperature = metrics.temperature as f64;
        
        if temperature <= 60.0 {
            100.0
        } else if temperature <= 70.0 {
            90.0
        } else if temperature <= 80.0 {
            80.0
        } else if temperature <= 85.0 {
            60.0
        } else if temperature <= 90.0 {
            40.0
        } else {
            20.0
        }
    }
    
    fn calculate_power_score(&self, metrics: &GpuMetrics) -> f64 {
        let power_draw = metrics.power_draw as f64;
        
        // Calculate efficiency score based on utilization vs power
        let utilization = metrics.utilization_gpu as f64;
        let efficiency = if power_draw > 0.0 { utilization / power_draw * 100.0 } else { 0.0 };
        
        if efficiency >= 0.5 {
            100.0
        } else if efficiency >= 0.4 {
            80.0
        } else if efficiency >= 0.3 {
            60.0
        } else if efficiency >= 0.2 {
            40.0
        } else {
            20.0
        }
    }
    
    fn calculate_utilization_score(&self, metrics: &GpuMetrics) -> f64 {
        let utilization = metrics.utilization_gpu as f64;
        
        // Optimal utilization is between 70-90%
        if utilization >= 70.0 && utilization <= 90.0 {
            100.0
        } else if utilization >= 50.0 && utilization < 70.0 {
            80.0
        } else if utilization > 90.0 && utilization <= 100.0 {
            70.0
        } else if utilization >= 20.0 && utilization < 50.0 {
            60.0
        } else {
            40.0
        }
    }
    
    fn calculate_memory_score(&self, metrics: &GpuMetrics) -> f64 {
        let memory_usage_ratio = metrics.memory_used as f64 / metrics.memory_total as f64;
        
        if memory_usage_ratio <= 0.7 {
            100.0
        } else if memory_usage_ratio <= 0.8 {
            80.0
        } else if memory_usage_ratio <= 0.9 {
            60.0
        } else if memory_usage_ratio <= 0.95 {
            40.0
        } else {
            20.0
        }
    }
    
    fn calculate_ecc_score(&self, metrics: &GpuMetrics) -> f64 {
        let correctable_errors = metrics.ecc_errors_correctable.unwrap_or(0);
        let uncorrectable_errors = metrics.ecc_errors_uncorrectable.unwrap_or(0);
        
        if uncorrectable_errors > 0 {
            0.0 // Critical - uncorrectable errors
        } else if correctable_errors > 100 {
            20.0 // High correctable error count
        } else if correctable_errors > 50 {
            40.0
        } else if correctable_errors > 10 {
            60.0
        } else if correctable_errors > 0 {
            80.0
        } else {
            100.0 // No errors
        }
    }
    
    fn determine_health_status(&self, health_score: f64) -> HealthStatus {
        match health_score {
            score if score >= 90.0 => HealthStatus::Excellent,
            score if score >= 80.0 => HealthStatus::Good,
            score if score >= 70.0 => HealthStatus::Fair,
            score if score >= 60.0 => HealthStatus::Poor,
            score if score >= 50.0 => HealthStatus::Critical,
            _ => HealthStatus::Emergency,
        }
    }
    
    fn generate_health_recommendations(&self, gpu_id: &str, health_metric: &HealthMetric) -> Vec<HealthRecommendation> {
        let mut recommendations = Vec::new();
        
        // Temperature-based recommendations
        if health_metric.temperature_score < 60.0 {
            recommendations.push(HealthRecommendation {
                title: "Clean Cooling System".to_string(),
                description: "GPU temperature is high. Clean dust from cooling system and check fan operation.".to_string(),
                priority: RecommendationPriority::High,
                action: HealthAction::CleanCoolingSystem,
                expected_benefit: 0.3,
                urgency: Urgency::High,
            });
            
            if health_metric.temperature_score < 40.0 {
                recommendations.push(HealthRecommendation {
                    title: "Replace Thermal Paste".to_string(),
                    description: "Critical temperature levels detected. Consider replacing thermal paste.".to_string(),
                    priority: RecommendationPriority::Critical,
                    action: HealthAction::ReplaceThermalPaste,
                    expected_benefit: 0.5,
                    urgency: Urgency::Critical,
                });
            }
        }
        
        // Power-based recommendations
        if health_metric.power_score < 60.0 {
            recommendations.push(HealthRecommendation {
                title: "Check Power Connections".to_string(),
                description: "Power efficiency is low. Check power connections and PSU capacity.".to_string(),
                priority: RecommendationPriority::Medium,
                action: HealthAction::CheckPowerConnections,
                expected_benefit: 0.2,
                urgency: Urgency::Medium,
            });
        }
        
        // Utilization-based recommendations
        if health_metric.utilization_score < 60.0 {
            recommendations.push(HealthRecommendation {
                title: "Monitor Performance".to_string(),
                description: "GPU utilization is outside optimal range. Monitor for performance issues.".to_string(),
                priority: RecommendationPriority::Low,
                action: HealthAction::MonitorTemperature,
                expected_benefit: 0.1,
                urgency: Urgency::Low,
            });
        }
        
        // Memory-based recommendations
        if health_metric.memory_score < 60.0 {
            recommendations.push(HealthRecommendation {
                title: "Memory Management".to_string(),
                description: "High memory usage detected. Consider optimizing memory usage or upgrading memory.".to_string(),
                priority: RecommendationPriority::Medium,
                action: HealthAction::Custom("Optimize memory usage".to_string()),
                expected_benefit: 0.25,
                urgency: Urgency::Medium,
            });
        }
        
        // ECC-based recommendations
        if health_metric.ecc_score < 60.0 {
            recommendations.push(HealthRecommendation {
                title: "ECC Error Investigation".to_string(),
                description: "ECC errors detected. Investigate memory stability and consider hardware replacement.".to_string(),
                priority: RecommendationPriority::Critical,
                action: HealthAction::ReplaceHardware,
                expected_benefit: 0.4,
                urgency: Urgency::Critical,
            });
        }
        
        // General maintenance recommendations
        if let Some(schedule) = self.maintenance_schedule.get(gpu_id) {
            if let Some(next_maintenance) = schedule.next_scheduled {
                let time_until_maintenance = next_maintenance.duration_since(SystemTime::now()).unwrap_or_default();
                if time_until_maintenance < Duration::from_secs(7 * 24 * 3600) { // 1 week
                    recommendations.push(HealthRecommendation {
                        title: "Schedule Maintenance".to_string(),
                        description: "Scheduled maintenance is due soon.".to_string(),
                        priority: RecommendationPriority::Medium,
                        action: HealthAction::ScheduleMaintenance,
                        expected_benefit: 0.2,
                        urgency: Urgency::Medium,
                    });
                }
            }
        }
        
        recommendations
    }
    
    fn identify_risk_factors(&self, gpu_id: &str, health_metric: &HealthMetric) -> Vec<RiskFactor> {
        let mut risk_factors = Vec::new();
        
        // Temperature risk
        if health_metric.temperature_score < 60.0 {
            risk_factors.push(RiskFactor {
                factor_type: RiskFactorType::TemperatureRisk,
                severity: (100.0 - health_metric.temperature_score) / 100.0,
                description: "High operating temperature increases risk of thermal damage".to_string(),
                mitigation: "Improve cooling system, clean dust, replace thermal paste".to_string(),
                confidence: 0.9,
            });
        }
        
        // Power risk
        if health_metric.power_score < 60.0 {
            risk_factors.push(RiskFactor {
                factor_type: RiskFactorType::PowerRisk,
                severity: (100.0 - health_metric.power_score) / 100.0,
                description: "Power inefficiency may indicate hardware degradation".to_string(),
                mitigation: "Check power connections, monitor PSU health".to_string(),
                confidence: 0.7,
            });
        }
        
        // Memory risk
        if health_metric.memory_score < 60.0 {
            risk_factors.push(RiskFactor {
                factor_type: RiskFactorType::MemoryRisk,
                severity: (100.0 - health_metric.memory_score) / 100.0,
                description: "High memory usage may lead to performance degradation".to_string(),
                mitigation: "Optimize memory usage, consider memory upgrade".to_string(),
                confidence: 0.8,
            });
        }
        
        // ECC risk
        if health_metric.ecc_score < 80.0 {
            risk_factors.push(RiskFactor {
                factor_type: RiskFactorType::EccRisk,
                severity: (100.0 - health_metric.ecc_score) / 100.0,
                description: "ECC errors indicate potential memory hardware issues".to_string(),
                mitigation: "Monitor ECC errors, consider memory replacement".to_string(),
                confidence: 0.95,
            });
        }
        
        // Utilization risk
        if health_metric.utilization_score < 50.0 || health_metric.utilization_score > 90.0 {
            risk_factors.push(RiskFactor {
                factor_type: RiskFactorType::UtilizationRisk,
                severity: 0.3,
                description: "Suboptimal utilization may indicate performance issues".to_string(),
                mitigation: "Optimize workload distribution, check for bottlenecks".to_string(),
                confidence: 0.6,
            });
        }
        
        risk_factors
    }
    
    fn check_maintenance_needed(&self, gpu_id: &str, health_metric: &HealthMetric) -> bool {
        // Check if any health score is below threshold
        if health_metric.temperature_score < 50.0 ||
           health_metric.power_score < 50.0 ||
           health_metric.memory_score < 50.0 ||
           health_metric.ecc_score < 50.0 {
            return true;
        }
        
        // Check if overall health is poor
        if health_metric.overall_health < 60.0 {
            return true;
        }
        
        // Check scheduled maintenance
        if let Some(schedule) = self.maintenance_schedule.get(gpu_id) {
            if let Some(next_maintenance) = schedule.next_scheduled {
                if SystemTime::now() >= next_maintenance {
                    return true;
                }
            }
        }
        
        false
    }
    
    fn calculate_next_maintenance(&self, gpu_id: &str) -> Option<SystemTime> {
        if let Some(schedule) = self.maintenance_schedule.get(gpu_id) {
            schedule.next_scheduled
        } else {
            // Default maintenance schedule - every 6 months
            Some(SystemTime::now() + Duration::from_secs(6 * 30 * 24 * 3600))
        }
    }
    
    fn update_predictive_models(&mut self, gpu_id: &str, health_metric: &HealthMetric) {
        // Update temperature trend model
        if let Some(model) = self.predictive_models.get_mut(gpu_id) {
            // Update model predictions based on current data
            // This is a simplified implementation
            model.last_trained = SystemTime::now();
        } else {
            // Create new predictive model
            let model = PredictiveModel {
                gpu_id: gpu_id.to_string(),
                model_type: ModelType::TemperatureTrend,
                accuracy: 0.8,
                last_trained: SystemTime::now(),
                predictions: Vec::new(),
            };
            self.predictive_models.insert(gpu_id.to_string(), model);
        }
    }
    
    pub fn schedule_maintenance(&mut self, gpu_id: &str, maintenance_type: MaintenanceType, description: String) {
        let maintenance_record = MaintenanceRecord {
            timestamp: SystemTime::now(),
            maintenance_type: maintenance_type.clone(),
            description,
            performed_by: "System".to_string(),
            health_improvement: 0.0, // Will be updated after maintenance
        };
        
        let schedule = self.maintenance_schedule.entry(gpu_id.to_string())
            .or_insert_with(|| MaintenanceSchedule {
                gpu_id: gpu_id.to_string(),
                last_maintenance: None,
                next_scheduled: None,
                maintenance_interval: Duration::from_secs(6 * 30 * 24 * 3600), // 6 months
                maintenance_type: MaintenanceType::Preventive,
                maintenance_history: Vec::new(),
            });
        
        schedule.maintenance_history.push(maintenance_record);
        schedule.last_maintenance = Some(SystemTime::now());
        
        // Schedule next maintenance
        schedule.next_scheduled = Some(SystemTime::now() + schedule.maintenance_interval);
    }
    
    pub fn get_health_history(&self, gpu_id: &str) -> Option<&VecDeque<HealthMetric>> {
        self.health_history.get(gpu_id)
    }
    
    pub fn get_health_score(&self, gpu_id: &str) -> Option<f64> {
        self.health_scores.get(gpu_id).copied()
    }
    
    pub fn get_maintenance_schedule(&self, gpu_id: &str) -> Option<&MaintenanceSchedule> {
        self.maintenance_schedule.get(gpu_id)
    }
    
    pub fn get_predictive_model(&self, gpu_id: &str) -> Option<&PredictiveModel> {
        self.predictive_models.get(gpu_id)
    }
    
    pub fn update_health_thresholds(&mut self, thresholds: HealthThresholds) {
        self.health_thresholds = thresholds;
    }
    
    pub fn get_health_thresholds(&self) -> &HealthThresholds {
        &self.health_thresholds
    }
}
