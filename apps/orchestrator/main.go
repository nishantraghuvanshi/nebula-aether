package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	"github.com/jackc/pgx/v4"
	"github.com/jackc/pgx/v4/pgxpool"
	"github.com/nats-io/nats.go"
)

// This struct must match the Rust agent's GpuTelemetry struct
type GpuTelemetry struct {
	GpuID                       string `json:"gpu_id"`
	GpuName                     string `json:"gpu_name"`
	UtilizationGpu              uint32 `json:"utilization_gpu"`
	UtilizationMemoryController uint32 `json:"utilization_memory_controller"`
	PerformanceState            string `json:"performance_state"`
	ClockGpuMhz                 uint32 `json:"clock_gpu_mhz"`
	ClockMemMhz                 uint32 `json:"clock_mem_mhz"`
	MemoryUsedMb                uint64 `json:"memory_used_mb"`
	MemoryTotalMb               uint64 `json:"memory_total_mb"`
	TemperatureC                uint32 `json:"temperature_c"`
	PowerDrawW                  uint32 `json:"power_draw_w"`
	ThrottlingReasons           string `json:"throttling_reasons"`
}

// Job struct to define a workload
type Job struct {
	ID              string   `json:"id"`
	Type            string   `json:"type"` // e.g., "training" or "inference"
	Name            string   `json:"name,omitempty"`
	Description     string   `json:"description,omitempty"`
	Script          string   `json:"script,omitempty"`
	Args            []string `json:"args,omitempty"`
	MinMemoryMB     int      `json:"min_memory_mb,omitempty"`
	MaxDurationSec  int      `json:"max_duration_sec,omitempty"`
	Priority        string   `json:"priority,omitempty"`
	ExpectedGpuUtil int      `json:"expected_gpu_util,omitempty"`
}

// JobExecution struct for sending execution commands
type JobExecution struct {
	JobID  string   `json:"job_id"`
	Type   string   `json:"job_type"`
	Script string   `json:"script"`
	Args   []string `json:"args"`
	GpuID  string   `json:"gpu_id"`
}

// PerformanceMetrics struct to match Rust agent's performance data
type PerformanceMetrics struct {
	// Core Performance Metrics
	Throughput         *float64 `json:"throughput,omitempty"`
	SamplesPerSecond   *float64 `json:"samples_per_second,omitempty"`
	CompletionTimeSec  *float64 `json:"completion_time_sec,omitempty"`
	Accuracy           *float64 `json:"accuracy,omitempty"`

	// Resource Efficiency
	MemoryEfficiency         *float64 `json:"memory_efficiency,omitempty"`
	ComputationalEfficiency  *float64 `json:"computational_efficiency,omitempty"`
	PeakMemoryUsageMB        *uint64  `json:"peak_memory_usage_mb,omitempty"`

	// Job-Specific Metrics
	FramesProcessed      *uint64 `json:"frames_processed,omitempty"`
	BatchesProcessed     *uint64 `json:"batches_processed,omitempty"`
	IterationsCompleted  *uint64 `json:"iterations_completed,omitempty"`
	FinalResult          *string `json:"final_result,omitempty"`

	// Quality Metrics
	ErrorRate           *float64 `json:"error_rate,omitempty"`
	ConvergenceAchieved *bool    `json:"convergence_achieved,omitempty"`
	QualityScore        *float64 `json:"quality_score,omitempty"`

	// Resource Usage Patterns
	AvgGpuUtilization *float64 `json:"avg_gpu_utilization,omitempty"`
	MaxGpuUtilization *float64 `json:"max_gpu_utilization,omitempty"`
	ThermalEvents     *uint32  `json:"thermal_events,omitempty"`
}

// Enhanced JobStatus struct for receiving comprehensive status updates
type JobStatus struct {
	JobID     string `json:"job_id"`
	GpuID     string `json:"gpu_id"`
	JobType   string `json:"job_type,omitempty"`   // Added for performance tracking
	Status    string `json:"status"` // "started", "running", "completed", "failed"
	Message   string `json:"message"`
	StartTime *int64 `json:"start_time,omitempty"`
	StartedAt *time.Time `json:"started_at,omitempty"` // Added for performance tracking
	EndTime   *int64 `json:"end_time,omitempty"`
	ExitCode  *int   `json:"exit_code,omitempty"`

	// Enhanced Performance Data
	PerformanceMetrics *PerformanceMetrics `json:"performance_metrics,omitempty"`
	JobSummary         *string             `json:"job_summary,omitempty"`
	RawOutputSample    *string             `json:"raw_output_sample,omitempty"`
}

// Represents the current state of a GPU, which we'll send to the AI
type GpuState struct {
	// Core telemetry
	GpuName                     string    `json:"gpu_name"`
	Temp                        uint32    `json:"gpu_temp"`
	MemUsed                     uint64    `json:"gpu_mem_used"`
	MemTotal                    uint64    `json:"gpu_mem_total"`
	UtilizationGpu              uint32    `json:"utilization_gpu"`
	UtilizationMemoryController uint32    `json:"utilization_memory_controller"`
	PowerDrawW                  uint32    `json:"power_draw_w"`
	ThrottlingReasons           string    `json:"throttling_reasons"`

	// Clock speeds
	ClockGpuMhz uint32 `json:"clock_gpu_mhz"`
	ClockMemMhz uint32 `json:"clock_mem_mhz"`

	// Performance state
	PerformanceState string `json:"performance_state"`

	// Telemetry tracking (not sent to dashboard)
	LastTelemetryUpdate time.Time `json:"-"`
}

// Enhanced GPU Candidate with all telemetry features
type GpuCandidate struct {
	GpuID   string `json:"gpu_id"`
	GpuName string `json:"gpu_name"`

	// Core telemetry
	Temp                        uint32 `json:"gpu_temp"`
	MemUsed                     uint64 `json:"gpu_mem_used"`
	MemTotal                    uint64 `json:"gpu_mem_total"`
	UtilizationGpu              uint32 `json:"utilization_gpu"`
	UtilizationMemoryController uint32 `json:"utilization_memory_controller"`
	PowerDrawW                  uint32 `json:"power_draw_w"`
	ThrottlingReasons           string `json:"throttling_reasons"`

	// Clock speeds
	ClockGpuMhz uint32 `json:"clock_gpu_mhz"`
	ClockMemMhz uint32 `json:"clock_mem_mhz"`

	// Performance state
	PerformanceState string `json:"performance_state"`
}

// Job requirements for enhanced scheduling
type JobRequirements struct {
	MinMemoryMB      int    `json:"min_memory_mb"`
	ExpectedGpuUtil  int    `json:"expected_gpu_util"`
	MaxDurationSec   int    `json:"max_duration_sec"`
	Priority         string `json:"priority"`         // "low", "normal", "high"
	ComputeIntensity string `json:"compute_intensity"` // "memory", "compute", "mixed"
}

// Enhanced PredictionRequest
type PredictionRequest struct {
	Candidates      []GpuCandidate    `json:"candidates"`
	JobType         string            `json:"job_type"`
	JobRequirements *JobRequirements  `json:"job_requirements,omitempty"`
}

// Enhanced PredictionResponse with intelligent scheduling
type PredictionResponse struct {
	BestGpuID           string                 `json:"best_gpu_id"`
	ConfidenceScore     float64                `json:"confidence_score"`
	PredictedPerf       float64                `json:"predicted_performance"`
	ThermalRisk         float64                `json:"thermal_risk"`
	MemoryRisk          float64                `json:"memory_risk"`
	Reasons             []string               `json:"reasons"`
	// NEW: Intelligent scheduling fields
	SchedulingDecision  string                 `json:"scheduling_decision"`  // "assign_now", "queue_short", "queue_long"
	EstimatedWaitTime   int                    `json:"estimated_wait_time"`  // seconds
	ResourceAvailability map[string]float64    `json:"resource_availability"`
	SchedulingReason    string                 `json:"scheduling_reason"`
}

// DashboardUpdate packages full cluster info for the dashboard
type DashboardUpdate struct {
	ClusterState    map[string]GpuState  `json:"cluster_state"`
	CarbonIntensity float64              `json:"carbon_intensity"`
	Anomalies       map[string]bool      `json:"anomalies"`
	JobStatus       map[string]JobStatus `json:"job_status"`
	JobQueue        []Job                `json:"job_queue"`
	CompletedJobs   []JobStatus          `json:"completed_jobs"`
}

// mockCarbonIntensity returns a placeholder carbon intensity value
func mockCarbonIntensity() float64 {
	// Simple oscillating mock between 100-500
	return 100 + float64(time.Now().Unix()%400)
}

// storeJobPerformanceData stores comprehensive job performance data for AI training
func storeJobPerformanceData(status JobStatus) error {
	if dbConn == nil {
		return fmt.Errorf("database connection not available")
	}

	// Calculate job duration and times
	var durationSeconds *int
	var startTime, endTime *time.Time
	now := time.Now()
	endTime = &now

	// Convert StartTime (unix timestamp) to time.Time if available
	if status.StartTime != nil {
		t := time.Unix(*status.StartTime, 0)
		startTime = &t
		duration := int(endTime.Sub(t).Seconds())
		durationSeconds = &duration
	}

	// Use StartedAt if available (fallback)
	if status.StartedAt != nil {
		startTime = status.StartedAt
		duration := int(endTime.Sub(*status.StartedAt).Seconds())
		durationSeconds = &duration
	}

	// Default job type if not provided
	jobType := status.JobType
	if jobType == "" {
		jobType = "general" // default type
	}

	// Calculate derived performance metrics
	var performanceScore, resourceEfficiency, thermalImpact, powerEfficiency, reliabilityScore *float64

	if status.PerformanceMetrics != nil {
		metrics := status.PerformanceMetrics

		// Calculate performance score (0-100) based on job completion and throughput
		var score float64 = 50 // baseline
		if status.Status == "completed" {
			score = 80 // successful completion
			if metrics.Throughput != nil && *metrics.Throughput > 0 {
				score += 20 // high throughput bonus
			}
		} else {
			score = 20 // failed/killed jobs
		}
		performanceScore = &score

		// Resource efficiency: utilization vs allocation
		if metrics.MemoryEfficiency != nil {
			resourceEfficiency = metrics.MemoryEfficiency
		} else {
			efficiency := 0.7 // default moderate efficiency
			resourceEfficiency = &efficiency
		}

		// Thermal impact (0-1, lower is better) - use placeholder since MaxTemperature doesn't exist
		impact := 0.5 // default moderate impact
		thermalImpact = &impact

		// Power efficiency: performance per watt - use placeholder since AvgPowerDraw doesn't exist
		efficiency := 1.0 // default efficiency
		powerEfficiency = &efficiency

		// Reliability score based on completion status
		reliability := 1.0
		if status.Status == "failed" {
			reliability = 0.0
		} else if status.Status == "killed" {
			reliability = 0.5
		}
		reliabilityScore = &reliability
	}

	// Set defaults if no performance metrics
	if performanceScore == nil {
		score := 50.0
		performanceScore = &score
	}
	if resourceEfficiency == nil {
		efficiency := 0.7
		resourceEfficiency = &efficiency
	}
	if thermalImpact == nil {
		impact := 0.5
		thermalImpact = &impact
	}
	if powerEfficiency == nil {
		efficiency := 1.0
		powerEfficiency = &efficiency
	}
	if reliabilityScore == nil {
		reliability := 1.0
		reliabilityScore = &reliability
	}

	// Insert into job_performance table using connection pool
	_, err := dbPool.Exec(context.Background(),
		`INSERT INTO job_performance (
			job_id, gpu_id, job_type, start_time, end_time, duration_seconds, exit_code,
			throughput, completion_time_sec, samples_per_second, memory_efficiency, computational_efficiency,
			avg_gpu_utilization, max_gpu_utilization, avg_memory_utilization, max_memory_usage_mb,
			avg_temperature, max_temperature, avg_power_draw, thermal_events,
			performance_score, resource_efficiency, thermal_impact, power_efficiency, reliability_score
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25)`,
		status.JobID,
		status.GpuID,
		jobType,
		startTime,
		endTime,
		durationSeconds,
		status.ExitCode,
		// Performance metrics (will be nil if not available)
		getFloat64Ptr(status.PerformanceMetrics, "throughput"),
		getFloat64Ptr(status.PerformanceMetrics, "completion_time_sec"),
		getFloat64Ptr(status.PerformanceMetrics, "samples_per_second"),
		getFloat64Ptr(status.PerformanceMetrics, "memory_efficiency"),
		getFloat64Ptr(status.PerformanceMetrics, "computational_efficiency"),
		getFloat64Ptr(status.PerformanceMetrics, "avg_gpu_utilization"),
		getFloat64Ptr(status.PerformanceMetrics, "max_gpu_utilization"),
		nil, // avg_memory_utilization - not available in struct
		getInt64Ptr(status.PerformanceMetrics, "peak_memory_usage_mb"),
		nil, // avg_temperature - not available in struct
		nil, // max_temperature - not available in struct
		nil, // avg_power_draw - not available in struct
		getUint32Ptr(status.PerformanceMetrics, "thermal_events"),
		performanceScore,
		resourceEfficiency,
		thermalImpact,
		powerEfficiency,
		reliabilityScore,
	)

	if err != nil {
		return fmt.Errorf("failed to insert job performance data: %v", err)
	}

	// Also insert into training_data table for AI model training
	startTimeStr := "null"
	if startTime != nil {
		startTimeStr = fmt.Sprintf(`"%s"`, startTime.Format(time.RFC3339))
	}

	featuresJSON := fmt.Sprintf(`{
		"gpu_id": "%s",
		"job_type": "%s",
		"start_time": %s,
		"system_load": 1
	}`, status.GpuID, jobType, startTimeStr)

	durationVal := 300 // default duration
	if durationSeconds != nil {
		durationVal = *durationSeconds
	}

	labelsJSON := fmt.Sprintf(`{
		"performance_score": %f,
		"resource_efficiency": %f,
		"completion_status": "%s",
		"duration_seconds": %d
	}`, *performanceScore, *resourceEfficiency, status.Status, durationVal)

	_, err = dbPool.Exec(context.Background(),
		`INSERT INTO training_data (
			job_id, gpu_id, features, labels, job_type, data_quality_score
		) VALUES ($1, $2, $3, $4, $5, $6)`,
		status.JobID,
		status.GpuID,
		featuresJSON,
		labelsJSON,
		jobType,
		1.0, // high quality data from actual execution
	)

	if err != nil {
		return fmt.Errorf("failed to insert training data: %v", err)
	}

	return nil
}

// Helper functions to safely extract values from PerformanceMetrics
func getFloat64Ptr(metrics *PerformanceMetrics, field string) *float64 {
	if metrics == nil {
		return nil
	}
	switch field {
	case "throughput":
		return metrics.Throughput
	case "completion_time_sec":
		return metrics.CompletionTimeSec
	case "samples_per_second":
		return metrics.SamplesPerSecond
	case "memory_efficiency":
		return metrics.MemoryEfficiency
	case "computational_efficiency":
		return metrics.ComputationalEfficiency
	case "avg_gpu_utilization":
		return metrics.AvgGpuUtilization
	case "max_gpu_utilization":
		return metrics.MaxGpuUtilization
	// Note: avg_memory_utilization and avg_power_draw don't exist in struct
	}
	return nil
}

func getIntPtr(metrics *PerformanceMetrics, field string) *int {
	if metrics == nil {
		return nil
	}
	// Note: temperature fields don't exist in PerformanceMetrics struct
	// thermal_events is handled by getUint32Ptr
	return nil
}

func getInt64Ptr(metrics *PerformanceMetrics, field string) *int64 {
	if metrics == nil {
		return nil
	}
	switch field {
	case "peak_memory_usage_mb":
		if metrics.PeakMemoryUsageMB != nil {
			val := int64(*metrics.PeakMemoryUsageMB)
			return &val
		}
	}
	return nil
}

func getUint32Ptr(metrics *PerformanceMetrics, field string) *uint32 {
	if metrics == nil {
		return nil
	}
	switch field {
	case "thermal_events":
		return metrics.ThermalEvents
	}
	return nil
}

// checkAllAnomalies flags GPUs with simple heuristics
func checkAllAnomalies(state map[string]GpuState) map[string]bool {
	out := make(map[string]bool, len(state))
	for id, s := range state {
		// Example heuristic: high temp or throttling string not empty
		isHot := s.Temp >= 85
		throttling := s.ThrottlingReasons != "" && s.ThrottlingReasons != "None" && s.ThrottlingReasons != "[]"
		out[id] = isHot || throttling
	}
	return out
}

// WebSocket upgrader for dashboard connections
var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin:     func(r *http.Request) bool { return true }, // Allow all origins for dev
}

// Global variables to hold the current state
var (
	jobQueue        = make([]Job, 0)
	queueMux        = &sync.Mutex{}
	clusterState    = make(map[string]GpuState)
	clusterStateMux = &sync.RWMutex{}
	latestGpuState  = GpuState{}
	gpuStateMux     = &sync.RWMutex{}
	natsClient      *nats.Conn
	dbConn          *pgx.Conn        // Legacy single connection (deprecated)
	dbPool          *pgxpool.Pool    // Database connection pool for high-throughput operations
	jobDefinitions  = make(map[string]Job)        // Job definitions by ID
	activeJobStatus = make(map[string]JobStatus)  // Current job status by job ID
	completedJobs   = make([]JobStatus, 0)        // Recently completed jobs
	jobStatusMux    = &sync.RWMutex{}
	// NEW: Resource tracking for intelligent scheduling
	pendingJobsByGpu = make(map[string][]Job)     // Jobs assigned but not yet started per GPU
	runningJobsByGpu = make(map[string][]Job)     // Currently running jobs per GPU
	resourceMux      = &sync.RWMutex{}            // Mutex for resource tracking
	jobAssignmentMux = &sync.Mutex{}              // Prevents race conditions in job assignment
	// NEW: Enhanced logging system
	jobFlowLogger *os.File    // Detailed job flow logging
	aiLogger      *os.File    // AI decision logging
	resourceLogger *os.File   // Resource tracking logging
)

// loadJobDefinitions loads job definitions from the JSON file
func loadJobDefinitions() error {
	// Try multiple paths to find the job definitions file
	possiblePaths := []string{
		"./demo-jobs/job-definitions.json",
		"../demo-jobs/job-definitions.json",
		"../../demo-jobs/job-definitions.json",
	}

	var file *os.File
	var err error
	var filePath string

	for _, path := range possiblePaths {
		file, err = os.Open(path)
		if err == nil {
			filePath = path
			break
		}
	}

	if err != nil {
		return fmt.Errorf("failed to find job definitions file in any of these paths: %v", possiblePaths)
	}
	defer file.Close()

	log.Printf("📂 Loading job definitions from: %s", filePath)

	data, err := ioutil.ReadAll(file)
	if err != nil {
		return fmt.Errorf("failed to read job definitions file: %v", err)
	}

	var jobs []Job
	if err := json.Unmarshal(data, &jobs); err != nil {
		return fmt.Errorf("failed to parse job definitions: %v", err)
	}

	// Index jobs by ID for quick lookup
	for _, job := range jobs {
		jobDefinitions[job.ID] = job
	}

	log.Printf("📋 Loaded %d job definitions", len(jobDefinitions))
	return nil
}

// NEW: Enhanced logging system functions

// initLoggingSystem initializes separate log files for different components
func initLoggingSystem() error {
	timestamp := time.Now().Format("2006-01-02_15-04-05")

	// Create logs directory if it doesn't exist
	os.MkdirAll("logs", 0755)

	var err error

	// Job flow logging - tracks job lifecycle
	jobFlowLogger, err = os.OpenFile(fmt.Sprintf("logs/job_flow_%s.log", timestamp),
		os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		return fmt.Errorf("failed to create job flow log: %v", err)
	}

	// AI decision logging - tracks AI scheduling decisions
	aiLogger, err = os.OpenFile(fmt.Sprintf("logs/ai_decisions_%s.log", timestamp),
		os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		return fmt.Errorf("failed to create AI log: %v", err)
	}

	// Resource tracking logging - tracks GPU resource usage
	resourceLogger, err = os.OpenFile(fmt.Sprintf("logs/resources_%s.log", timestamp),
		os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		return fmt.Errorf("failed to create resource log: %v", err)
	}

	// Write headers
	logJobFlow("SYSTEM", "INIT", "Job flow logging started", map[string]interface{}{})
	logAIDecision("SYSTEM", "INIT", "AI decision logging started", map[string]interface{}{})
	logResourceChange("SYSTEM", "INIT", "Resource tracking logging started", map[string]interface{}{})

	log.Println("📋 Enhanced logging system initialized")
	return nil
}

// logJobFlow logs job lifecycle events
func logJobFlow(jobID, event, message string, data map[string]interface{}) {
	if jobFlowLogger == nil {
		return
	}

	logEntry := map[string]interface{}{
		"timestamp": time.Now().Format("2006-01-02 15:04:05.000"),
		"job_id":    jobID,
		"event":     event,
		"message":   message,
		"data":      data,
	}

	if jsonData, err := json.Marshal(logEntry); err == nil {
		fmt.Fprintf(jobFlowLogger, "%s\n", string(jsonData))
		jobFlowLogger.Sync()
	}
}

// logAIDecision logs AI scheduling decisions with full context
func logAIDecision(jobID, decision, reason string, context map[string]interface{}) {
	if aiLogger == nil {
		return
	}

	logEntry := map[string]interface{}{
		"timestamp": time.Now().Format("2006-01-02 15:04:05.000"),
		"job_id":    jobID,
		"decision":  decision,
		"reason":    reason,
		"context":   context,
	}

	if jsonData, err := json.Marshal(logEntry); err == nil {
		fmt.Fprintf(aiLogger, "%s\n", string(jsonData))
		aiLogger.Sync()
	}
}

// logResourceChange logs GPU resource state changes
func logResourceChange(gpuID, event, message string, resourceData map[string]interface{}) {
	if resourceLogger == nil {
		return
	}

	logEntry := map[string]interface{}{
		"timestamp":     time.Now().Format("2006-01-02 15:04:05.000"),
		"gpu_id":        gpuID,
		"event":         event,
		"message":       message,
		"resource_data": resourceData,
	}

	if jsonData, err := json.Marshal(logEntry); err == nil {
		fmt.Fprintf(resourceLogger, "%s\n", string(jsonData))
		resourceLogger.Sync()
	}
}

// closeLoggingSystem closes all log files
func closeLoggingSystem() {
	if jobFlowLogger != nil {
		jobFlowLogger.Close()
	}
	if aiLogger != nil {
		aiLogger.Close()
	}
	if resourceLogger != nil {
		resourceLogger.Close()
	}
}

// createJobRequirements creates job requirements from job definition
func createJobRequirements(job Job) *JobRequirements {
	if job.MinMemoryMB == 0 && job.ExpectedGpuUtil == 0 {
		return nil // No requirements specified
	}

	// Set defaults for missing fields
	priority := job.Priority
	if priority == "" {
		priority = "normal"
	}

	// Determine compute intensity based on job type
	computeIntensity := "mixed"
	switch job.Type {
	case "training":
		computeIntensity = "compute"
	case "inference":
		computeIntensity = "memory"
	case "memory":
		computeIntensity = "memory"
	case "compute":
		computeIntensity = "compute"
	}

	return &JobRequirements{
		MinMemoryMB:      job.MinMemoryMB,
		ExpectedGpuUtil:  job.ExpectedGpuUtil,
		MaxDurationSec:   job.MaxDurationSec,
		Priority:         priority,
		ComputeIntensity: computeIntensity,
	}
}

// askAICorePrediction sends all GPU candidates to the AI service and gets full scheduling prediction
func askAICorePrediction(cluster map[string]GpuState, job Job) (*PredictionResponse, error) {
	aiCoreURL := "http://localhost:8000/predict"

	candidates := make([]GpuCandidate, 0, len(cluster))
	for id, s := range cluster {
		// NEW: Calculate projected resource usage including pending/running jobs
		currentMem, projectedMem, currentCompute, projectedCompute := calculateGpuResourceUsage(id, s)

		// Use projected values for AI decision making to prevent resource conflicts
		adjustedMemUsed := uint64(projectedMem)
		adjustedGpuUtil := uint32(projectedCompute)

		// Ensure values don't exceed maximums
		if adjustedMemUsed > s.MemTotal {
			adjustedMemUsed = s.MemTotal
		}
		if adjustedGpuUtil > 100 {
			adjustedGpuUtil = 100
		}

		candidates = append(candidates, GpuCandidate{
			GpuID:   id,
			GpuName: s.GpuName,

			// Core telemetry - enhanced with projected resource usage
			Temp:                        s.Temp,
			MemUsed:                     adjustedMemUsed,  // NEW: Use projected memory
			MemTotal:                    s.MemTotal,
			UtilizationGpu:              adjustedGpuUtil,  // NEW: Use projected compute
			UtilizationMemoryController: s.UtilizationMemoryController,
			PowerDrawW:                  s.PowerDrawW,
			ThrottlingReasons:           s.ThrottlingReasons,

			// Clock speeds
			ClockGpuMhz: s.ClockGpuMhz,
			ClockMemMhz: s.ClockMemMhz,

			// Performance state
			PerformanceState: s.PerformanceState,
		})

		// Enhanced logging for resource projection
		resourceSummary := getGpuResourceSummary(id, s)
		log.Printf("🔮 GPU %s resource projection: Current: %.0fMB/%.0f%%, Projected: %.0fMB/%.0f%% (P:%0.f R:%.0f)",
			id, currentMem, currentCompute, projectedMem, projectedCompute,
			resourceSummary["pending_jobs"], resourceSummary["running_jobs"])
	}

	request := PredictionRequest{
		Candidates:      candidates,
		JobType:         job.Type,
		JobRequirements: createJobRequirements(job),
	}

	requestBody, err := json.Marshal(request)
	if err != nil {
		return nil, err
	}

	resp, err := http.Post(aiCoreURL, "application/json", bytes.NewBuffer(requestBody))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var predictionResp PredictionResponse
	if err := json.NewDecoder(resp.Body).Decode(&predictionResp); err != nil {
		return nil, err
	}

	// Log enhanced prediction results including scheduling
	log.Printf("🤖 AI Prediction Results:")
	log.Printf("   Selected GPU: %s", predictionResp.BestGpuID)
	log.Printf("   Confidence: %.1f%%", predictionResp.ConfidenceScore*100)
	log.Printf("   Predicted Performance: %.1f%%", predictionResp.PredictedPerf)
	log.Printf("   Thermal Risk: %.1f%%", predictionResp.ThermalRisk*100)
	log.Printf("   Memory Risk: %.1f%%", predictionResp.MemoryRisk*100)
	log.Printf("   📋 Scheduling Decision: %s (wait: %ds)", predictionResp.SchedulingDecision, predictionResp.EstimatedWaitTime)
	log.Printf("   📋 Scheduling Reason: %s", predictionResp.SchedulingReason)
	for _, reason := range predictionResp.Reasons {
		log.Printf("   %s", reason)
	}

	return &predictionResp, nil
}

// NEW: Resource management functions for intelligent scheduling

// calculateGpuResourceUsage calculates current and projected resource usage for a GPU
func calculateGpuResourceUsage(gpuID string, gpuState GpuState) (currentMemory, projectedMemory, currentCompute, projectedCompute float64) {
	resourceMux.RLock()
	defer resourceMux.RUnlock()

	// Current resource usage from telemetry
	currentMemory = float64(gpuState.MemUsed)
	currentCompute = float64(gpuState.UtilizationGpu)

	// Add pending jobs resource requirements
	projectedMemory = currentMemory
	projectedCompute = currentCompute

	// Add memory and compute from pending jobs
	if pendingJobs, exists := pendingJobsByGpu[gpuID]; exists {
		for _, job := range pendingJobs {
			projectedMemory += float64(job.MinMemoryMB)
			projectedCompute += float64(job.ExpectedGpuUtil)
		}
	}

	// Add memory and compute from running jobs
	if runningJobs, exists := runningJobsByGpu[gpuID]; exists {
		for _, job := range runningJobs {
			projectedMemory += float64(job.MinMemoryMB) * 0.5 // Running jobs may use less than peak
			projectedCompute += float64(job.ExpectedGpuUtil) * 0.7 // Reduce estimated impact for running jobs
		}
	}

	return currentMemory, projectedMemory, currentCompute, projectedCompute
}

// sanitizeStaleGpuData resets GPU utilization to 0% if telemetry is older than 5 minutes
// This prevents AI scheduling from using stale high utilization data when agents aren't running
func sanitizeStaleGpuData(gpuState GpuState) GpuState {
	staleTelemetryThreshold := 5 * time.Minute

	if time.Since(gpuState.LastTelemetryUpdate) > staleTelemetryThreshold {
		log.Printf("⚠️ Stale telemetry detected for GPU (age: %v), resetting utilization to 0%%",
			time.Since(gpuState.LastTelemetryUpdate))

		// Reset utilization to idle state for stale data
		gpuState.UtilizationGpu = 0
		gpuState.UtilizationMemoryController = 0
		gpuState.PowerDrawW = 50 // Idle power consumption
		gpuState.ThrottlingReasons = ""
	}

	return gpuState
}

// sanitizeStaleResourceTracking clears pending/running jobs for GPUs with stale telemetry
// Called once for all GPUs before AI prediction to avoid resource conflicts from stale data
func sanitizeStaleResourceTracking(clusterState map[string]GpuState) {
	staleTelemetryThreshold := 5 * time.Minute

	resourceMux.Lock()
	defer resourceMux.Unlock()

	for gpuID, state := range clusterState {
		if time.Since(state.LastTelemetryUpdate) > staleTelemetryThreshold {
			// Clear pending and running job tracking for stale GPUs
			if _, exists := pendingJobsByGpu[gpuID]; exists {
				log.Printf("🧹 Clearing %d pending jobs from stale GPU %s", len(pendingJobsByGpu[gpuID]), gpuID)
				delete(pendingJobsByGpu, gpuID)
			}
			if _, exists := runningJobsByGpu[gpuID]; exists {
				log.Printf("🧹 Clearing %d running jobs from stale GPU %s", len(runningJobsByGpu[gpuID]), gpuID)
				delete(runningJobsByGpu, gpuID)
			}
		}
	}
}

// forceCleanIdleGpuResources clears resource tracking for GPUs that show 0% utilization
// This is a temporary fix to handle phantom resource tracking after system restarts
func forceCleanIdleGpuResources(clusterState map[string]GpuState) {
	resourceMux.Lock()
	defer resourceMux.Unlock()

	for gpuID, state := range clusterState {
		// If GPU shows 0% utilization, clear all resource tracking
		if state.UtilizationGpu == 0 {
			pendingCleared := 0
			runningCleared := 0

			if pending, exists := pendingJobsByGpu[gpuID]; exists {
				pendingCleared = len(pending)
				delete(pendingJobsByGpu, gpuID)
			}
			if running, exists := runningJobsByGpu[gpuID]; exists {
				runningCleared = len(running)
				delete(runningJobsByGpu, gpuID)
			}

			if pendingCleared > 0 || runningCleared > 0 {
				log.Printf("🧹 Force cleared phantom resources for idle GPU %s: %d pending, %d running jobs",
					gpuID, pendingCleared, runningCleared)
			}
		}
	}
}

// reserveGpuResources reserves resources when assigning a job to a GPU
func reserveGpuResources(gpuID string, job Job) {
	resourceMux.Lock()
	defer resourceMux.Unlock()

	// Add to pending jobs list
	if pendingJobsByGpu[gpuID] == nil {
		pendingJobsByGpu[gpuID] = make([]Job, 0)
	}
	pendingJobsByGpu[gpuID] = append(pendingJobsByGpu[gpuID], job)

	// ENHANCED LOGGING: Resource reservation
	logResourceChange(gpuID, "RESOURCE_RESERVED", "Resources reserved for pending job", map[string]interface{}{
		"job_id":             job.ID,
		"job_type":           job.Type,
		"reserved_memory_mb": job.MinMemoryMB,
		"reserved_gpu_util":  job.ExpectedGpuUtil,
		"pending_jobs_count": len(pendingJobsByGpu[gpuID]),
		"total_reserved_memory_mb": func() int {
			total := 0
			for _, j := range pendingJobsByGpu[gpuID] {
				total += j.MinMemoryMB
			}
			return total
		}(),
	})

	log.Printf("🔒 Reserved resources on %s for job %s: %dMB memory, %d%% GPU util",
		gpuID, job.ID, job.MinMemoryMB, job.ExpectedGpuUtil)
}

// moveJobToPendingToRunning moves a job from pending to running when it starts
func moveJobToPendingToRunning(gpuID string, jobID string) {
	resourceMux.Lock()
	defer resourceMux.Unlock()

	// Find and remove from pending
	if pendingJobs, exists := pendingJobsByGpu[gpuID]; exists {
		for i, job := range pendingJobs {
			if job.ID == jobID {
				// Remove from pending
				pendingJobsByGpu[gpuID] = append(pendingJobs[:i], pendingJobs[i+1:]...)

				// Add to running
				if runningJobsByGpu[gpuID] == nil {
					runningJobsByGpu[gpuID] = make([]Job, 0)
				}
				runningJobsByGpu[gpuID] = append(runningJobsByGpu[gpuID], job)

				// ENHANCED LOGGING: Job state transition
				logResourceChange(gpuID, "JOB_STARTED", "Job moved from pending to running", map[string]interface{}{
					"job_id":             job.ID,
					"job_type":           job.Type,
					"memory_mb":          job.MinMemoryMB,
					"gpu_util":           job.ExpectedGpuUtil,
					"pending_jobs_count": len(pendingJobsByGpu[gpuID]),
					"running_jobs_count": len(runningJobsByGpu[gpuID]),
				})

				logJobFlow(jobID, "STARTED", "Job execution started on GPU", map[string]interface{}{
					"gpu_id":             gpuID,
					"transition":         "pending_to_running",
					"pending_jobs_count": len(pendingJobsByGpu[gpuID]),
					"running_jobs_count": len(runningJobsByGpu[gpuID]),
				})

				log.Printf("🏃 Moved job %s from pending to running on %s", jobID, gpuID)
				break
			}
		}
	}
}

// releaseGpuResources releases resources when a job completes
func releaseGpuResources(gpuID string, jobID string) {
	resourceMux.Lock()
	defer resourceMux.Unlock()

	// Track which list the job was found in
	releaseType := "unknown"
	var releasedJob Job

	// Remove from running jobs
	if runningJobs, exists := runningJobsByGpu[gpuID]; exists {
		for i, job := range runningJobs {
			if job.ID == jobID {
				runningJobsByGpu[gpuID] = append(runningJobs[:i], runningJobs[i+1:]...)
				releaseType = "running"
				releasedJob = job
				log.Printf("🔓 Released resources on %s for completed job %s", gpuID, jobID)
				break
			}
		}
	}

	// Also check pending jobs (in case job was killed before starting)
	if pendingJobs, exists := pendingJobsByGpu[gpuID]; exists {
		for i, job := range pendingJobs {
			if job.ID == jobID {
				pendingJobsByGpu[gpuID] = append(pendingJobs[:i], pendingJobs[i+1:]...)
				if releaseType == "unknown" {
					releaseType = "pending"
					releasedJob = job
				}
				log.Printf("🔓 Released reserved resources on %s for job %s", gpuID, jobID)
				break
			}
		}
	}

	// ENHANCED LOGGING: Resource release
	if releaseType != "unknown" {
		logResourceChange(gpuID, "RESOURCE_RELEASED", "Resources released after job completion", map[string]interface{}{
			"job_id":             jobID,
			"job_type":           releasedJob.Type,
			"released_memory_mb": releasedJob.MinMemoryMB,
			"released_gpu_util":  releasedJob.ExpectedGpuUtil,
			"release_type":       releaseType,
			"pending_jobs_count": len(pendingJobsByGpu[gpuID]),
			"running_jobs_count": len(runningJobsByGpu[gpuID]),
			"remaining_reserved_memory_mb": func() int {
				total := 0
				for _, j := range pendingJobsByGpu[gpuID] {
					total += j.MinMemoryMB
				}
				for _, j := range runningJobsByGpu[gpuID] {
					total += j.MinMemoryMB
				}
				return total
			}(),
		})

		logJobFlow(jobID, "RESOURCES_RELEASED", "Job resources freed up", map[string]interface{}{
			"gpu_id":             gpuID,
			"release_type":       releaseType,
			"pending_jobs_count": len(pendingJobsByGpu[gpuID]),
			"running_jobs_count": len(runningJobsByGpu[gpuID]),
		})
	} else {
		// Job not found in either list - log this anomaly
		logResourceChange(gpuID, "RELEASE_ANOMALY", "Attempted to release resources for unknown job", map[string]interface{}{
			"job_id":             jobID,
			"pending_jobs_count": len(pendingJobsByGpu[gpuID]),
			"running_jobs_count": len(runningJobsByGpu[gpuID]),
		})
	}
}

// getGpuResourceSummary returns a summary of resource usage for dashboard/logging
func getGpuResourceSummary(gpuID string, gpuState GpuState) map[string]interface{} {
	currentMem, projectedMem, currentCompute, projectedCompute := calculateGpuResourceUsage(gpuID, gpuState)

	resourceMux.RLock()
	pendingCount := len(pendingJobsByGpu[gpuID])
	runningCount := len(runningJobsByGpu[gpuID])
	resourceMux.RUnlock()

	return map[string]interface{}{
		"current_memory_mb":    currentMem,
		"projected_memory_mb":  projectedMem,
		"current_compute_pct":  currentCompute,
		"projected_compute_pct": projectedCompute,
		"pending_jobs":         pendingCount,
		"running_jobs":         runningCount,
		"memory_available_mb":  float64(gpuState.MemTotal) - projectedMem,
		"compute_available_pct": 100.0 - projectedCompute,
	}
}

// askAICoreCandidates sends all GPU candidates to the AI service and gets the best GPU ID
func askAICoreCandidates(cluster map[string]GpuState, job Job) (string, error) {
	prediction, err := askAICorePrediction(cluster, job)
	if err != nil {
		return "", err
	}
	return prediction.BestGpuID, nil
}

// Legacy function - keeping for compatibility
func askAICoreCandidatesLegacy(cluster map[string]GpuState, job Job) (string, error) {
	aiCoreURL := "http://localhost:8000/predict"

	candidates := make([]GpuCandidate, 0, len(cluster))
	for id, s := range cluster {
		candidates = append(candidates, GpuCandidate{
			GpuID:   id,
			GpuName: s.GpuName,

			// Core telemetry - all fields from enhanced struct
			Temp:                        s.Temp,
			MemUsed:                     s.MemUsed,
			MemTotal:                    s.MemTotal,
			UtilizationGpu:              s.UtilizationGpu,
			UtilizationMemoryController: s.UtilizationMemoryController,
			PowerDrawW:                  s.PowerDrawW,
			ThrottlingReasons:           s.ThrottlingReasons,

			// Clock speeds
			ClockGpuMhz: s.ClockGpuMhz,
			ClockMemMhz: s.ClockMemMhz,

			// Performance state
			PerformanceState: s.PerformanceState,
		})
	}

	// Create job requirements from job definition
	jobRequirements := createJobRequirements(job)

	requestBody, err := json.Marshal(PredictionRequest{
		Candidates:      candidates,
		JobType:         job.Type,
		JobRequirements: jobRequirements,
	})
	if err != nil {
		return "", err
	}

	resp, err := http.Post(aiCoreURL, "application/json", bytes.NewBuffer(requestBody))
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	var predictionResp PredictionResponse
	if err := json.NewDecoder(resp.Body).Decode(&predictionResp); err != nil {
		return "", err
	}

	// Log enhanced prediction results
	log.Printf("🤖 AI Prediction Results:")
	log.Printf("   Selected GPU: %s", predictionResp.BestGpuID)
	log.Printf("   Confidence: %.1f%%", predictionResp.ConfidenceScore*100)
	log.Printf("   Predicted Performance: %.1f%%", predictionResp.PredictedPerf)
	log.Printf("   Thermal Risk: %.1f%%", predictionResp.ThermalRisk*100)
	log.Printf("   Memory Risk: %.1f%%", predictionResp.MemoryRisk*100)
	for _, reason := range predictionResp.Reasons {
		log.Printf("   %s", reason)
	}

	return predictionResp.BestGpuID, nil
}

// sendJobExecution sends a job execution command via NATS
func sendJobExecution(jobExec JobExecution) error {
	if natsClient == nil {
		return fmt.Errorf("NATS client not initialized")
	}

	// Serialize the job execution command
	commandData, err := json.Marshal(jobExec)
	if err != nil {
		return fmt.Errorf("failed to marshal job execution: %v", err)
	}

	// Send command to the specific GPU
	subject := fmt.Sprintf("aether.commands.%s", jobExec.GpuID)
	command := fmt.Sprintf("execute_job:%s", string(commandData))

	if err := natsClient.Publish(subject, []byte(command)); err != nil {
		return fmt.Errorf("failed to publish job command: %v", err)
	}

	log.Printf("📡 Published job execution command to %s", subject)
	return nil
}

// scheduleJobs is our main scheduling loop
func scheduleJobs() {
	ticker := time.NewTicker(5 * time.Second) // Check for jobs every 5 seconds
	defer ticker.Stop()

	for range ticker.C {
		queueMux.Lock()
		if len(jobQueue) == 0 {
			queueMux.Unlock()

			// POWER GATING LOGIC: No jobs in queue, predict idle period
			log.Println("No jobs in queue. Predicting idle period. Sending sleep command.")
			// Note: In a real implementation, we would need access to the NATS connection here
			// For now, we'll just log the intent
			log.Println("Would send sleep command to GPU agent")

			continue // No jobs to schedule
		}

		// Get the next job from the queue
		jobToSchedule := jobQueue[0]
		jobQueue = jobQueue[1:]
		queueMux.Unlock()

		// Get the most recent GPU state
		clusterStateMux.RLock()
		candidates := make([]GpuCandidate, 0, len(clusterState))
		for gpuID, state := range clusterState {
			candidates = append(candidates, GpuCandidate{
				GpuID:             gpuID,
				Temp:              state.Temp,
				MemUsed:           state.MemUsed,
				UtilizationGpu:    state.UtilizationGpu,
				PowerDrawW:        state.PowerDrawW,
				ThrottlingReasons: state.ThrottlingReasons,
			})
		}
		clusterStateMux.RUnlock()

		log.Printf("Attempting to schedule job %s. Candidates: %d",
			jobToSchedule.ID, len(candidates))

		// Ask the AI for a decision
		bestGpuID, err := askAICoreCandidates(clusterState, jobToSchedule)
		if err != nil {
			log.Printf("Error consulting AI core: %v. Re-queuing job.", err)
			// In a real system, you'd add the job back to the queue with better logic
			continue
		}

		log.Printf("AI approved! Scheduling job %s on GPU %s.", jobToSchedule.ID, bestGpuID)

		// Send job execution command via NATS
		jobExecution := JobExecution{
			JobID:  jobToSchedule.ID,
			Type:   jobToSchedule.Type,
			Script: jobToSchedule.Script,
			Args:   jobToSchedule.Args,
			GpuID:  bestGpuID,
		}

		if err := sendJobExecution(jobExecution); err != nil {
			log.Printf("Error sending job execution command: %v", err)
			// Could re-queue the job here
		} else {
			log.Printf("✅ Job execution command sent for %s on %s", jobToSchedule.ID, bestGpuID)
		}
	}
}

// graphqlHandler handles WebSocket connections for the dashboard
func graphqlHandler(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("Failed to upgrade connection: %v", err)
		return
	}
	defer conn.Close()

	log.Println("Dashboard connected.")

	// Periodically send the latest cluster snapshot to the dashboard
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		clusterStateMux.RLock()
		snapshot := make(map[string]GpuState, len(clusterState))
		for gpuID, state := range clusterState {
			snapshot[gpuID] = state
		}

		// Include job status in dashboard update
		jobStatusMux.RLock()
		jobStatusSnapshot := make(map[string]JobStatus, len(activeJobStatus))
		for jobID, status := range activeJobStatus {
			jobStatusSnapshot[jobID] = status
		}
		completedJobsSnapshot := make([]JobStatus, len(completedJobs))
		copy(completedJobsSnapshot, completedJobs)
		jobStatusMux.RUnlock()

		// Get job queue snapshot
		queueMux.Lock()
		jobQueueSnapshot := make([]Job, len(jobQueue))
		copy(jobQueueSnapshot, jobQueue)
		queueMux.Unlock()

		update := DashboardUpdate{
			ClusterState:    snapshot,
			CarbonIntensity: mockCarbonIntensity(),
			Anomalies:       checkAllAnomalies(snapshot),
			JobStatus:       jobStatusSnapshot,
			JobQueue:        jobQueueSnapshot,
			CompletedJobs:   completedJobsSnapshot,
		}
		clusterStateMux.RUnlock()

		// Marshal the update into JSON to send over WebSocket
		payload, _ := json.Marshal(update)

		if err := conn.WriteMessage(websocket.TextMessage, payload); err != nil {
			log.Println("Dashboard disconnected.")
			break
		}
	}
}

// CORS middleware
func corsMiddleware(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		next(w, r)
	}
}

// CORS handler for OPTIONS requests
func corsHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
	w.WriteHeader(http.StatusOK)
}

// The HTTP handler for submitting jobs
func handleSubmit(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Only POST method is allowed", http.StatusMethodNotAllowed)
		return
	}

	var jobSubmission struct {
		ID string `json:"id"`
	}

	if err := json.NewDecoder(r.Body).Decode(&jobSubmission); err != nil {
		log.Printf("❌ Failed to decode job submission JSON: %v", err)
		http.Error(w, "Invalid JSON: " + err.Error(), http.StatusBadRequest)
		return
	}

	log.Printf("📥 Received job submission: %+v", jobSubmission)

	// Validate required fields
	if jobSubmission.ID == "" {
		log.Printf("❌ Job submission missing ID")
		http.Error(w, "Job ID is required", http.StatusBadRequest)
		return
	}

	log.Printf("🔍 Looking up job definition for ID: %s", jobSubmission.ID)
	log.Printf("📋 Available job definitions: %v", func() []string {
		keys := make([]string, 0, len(jobDefinitions))
		for k := range jobDefinitions {
			keys = append(keys, k)
		}
		return keys
	}())

	// Look up job definition
	jobDef, exists := jobDefinitions[jobSubmission.ID]
	if !exists {
		log.Printf("❌ Job definition not found: %s", jobSubmission.ID)
		http.Error(w, fmt.Sprintf("Job definition not found: %s. Available jobs: %v", jobSubmission.ID, func() []string {
			keys := make([]string, 0, len(jobDefinitions))
			for k := range jobDefinitions {
				keys = append(keys, k)
			}
			return keys
		}()), http.StatusNotFound)
		return
	}

	log.Printf("✅ Found job definition: %+v", jobDef)

	// Add the complete job to the queue
	queueMux.Lock()
	jobQueue = append(jobQueue, jobDef)
	queueMux.Unlock()

	// ENHANCED LOGGING: Job submission
	logJobFlow(jobDef.ID, "SUBMITTED", "Job added to queue", map[string]interface{}{
		"job_type":          jobDef.Type,
		"job_name":          jobDef.Name,
		"min_memory_mb":     jobDef.MinMemoryMB,
		"expected_gpu_util": jobDef.ExpectedGpuUtil,
		"max_duration_sec":  jobDef.MaxDurationSec,
		"priority":          jobDef.Priority,
		"queue_position":    len(jobQueue),
	})

	log.Printf("📥 Added job to queue: %s (%s) - %s", jobDef.ID, jobDef.Type, jobDef.Name)
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status": "job added",
		"job": map[string]interface{}{
			"id":          jobDef.ID,
			"type":        jobDef.Type,
			"name":        jobDef.Name,
			"description": jobDef.Description,
		},
	})
}

func handleKill(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Only POST method is allowed", http.StatusMethodNotAllowed)
		return
	}

	// Extract job ID from URL path
	jobID := r.URL.Path[len("/kill/"):]
	if jobID == "" {
		http.Error(w, "Job ID is required", http.StatusBadRequest)
		return
	}

	log.Printf("🔴 Kill request for job: %s", jobID)

	// Check if job is currently running
	jobStatusMux.RLock()
	status, exists := activeJobStatus[jobID]
	jobStatusMux.RUnlock()

	if !exists {
		http.Error(w, fmt.Sprintf("Job %s not found or not running", jobID), http.StatusNotFound)
		return
	}

	if status.Status != "running" {
		http.Error(w, fmt.Sprintf("Job %s is not running (status: %s)", jobID, status.Status), http.StatusBadRequest)
		return
	}

	// Send kill command via NATS
	killCommand := fmt.Sprintf("kill_job:%s", jobID)
	if err := natsClient.Publish("aether.commands.all", []byte(killCommand)); err != nil {
		log.Printf("Error sending kill command: %v", err)
		http.Error(w, "Failed to send kill command", http.StatusInternalServerError)
		return
	}

	log.Printf("📡 Sent kill command for job: %s", jobID)
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":  "kill command sent",
		"job_id":  jobID,
		"message": fmt.Sprintf("Kill command sent for job %s", jobID),
	})
}

func handlePoll(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Only GET method is allowed", http.StatusMethodNotAllowed)
		return
	}

	// Get GPU ID from query parameter
	gpuID := r.URL.Query().Get("gpu_id")
	if gpuID == "" {
		http.Error(w, "gpu_id parameter is required", http.StatusBadRequest)
		return
	}

	// Check if there's a job in the queue
	queueMux.Lock()
	if len(jobQueue) == 0 {
		queueMux.Unlock()
		// No jobs available
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"job": nil,
			"message": "no jobs available",
		})
		return
	}

	// Get the next job from the queue (but don't remove it yet)
	nextJob := jobQueue[0]
	queueMux.Unlock()

	// Check if this GPU is suitable for the job using AI prediction
	clusterStateMux.RLock()
	currentClusterState := make(map[string]GpuState, len(clusterState))
	for id, state := range clusterState {
		// Sanitize stale telemetry data before AI prediction
		currentClusterState[id] = sanitizeStaleGpuData(state)
	}
	clusterStateMux.RUnlock()

	// Clear resource tracking for stale GPUs to prevent resource conflicts
	sanitizeStaleResourceTracking(currentClusterState)

	// DEBUG: Force clear resource tracking for idle GPUs (temporary fix)
	forceCleanIdleGpuResources(currentClusterState)

	// Ensure the requesting GPU is in our cluster state
	_, gpuExists := currentClusterState[gpuID]
	if !gpuExists {
		log.Printf("⚠️ GPU %s not found in cluster state, allowing job assignment", gpuID)
		// Allow the job to proceed for unknown GPUs (fallback behavior)
	} else {
		// Use AI to determine the best GPU and scheduling decision for this job
		if len(currentClusterState) > 1 {
			log.Printf("🤖 Using AI to evaluate job %s for GPU %s", nextJob.ID, gpuID)

			prediction, err := askAICorePrediction(currentClusterState, nextJob)
			if err != nil {
				log.Printf("AI prediction failed: %v. Allowing job on requesting GPU %s", err, gpuID)

				// ENHANCED LOGGING: AI prediction failure
				logAIDecision(nextJob.ID, "PREDICTION_FAILED", "AI service unavailable", map[string]interface{}{
					"requesting_gpu": gpuID,
					"error":          err.Error(),
					"fallback":       "allow_on_requesting_gpu",
				})
			} else {
				// ENHANCED LOGGING: AI prediction success
				aiContext := map[string]interface{}{
					"requesting_gpu":       gpuID,
					"recommended_gpu":      prediction.BestGpuID,
					"scheduling_decision":  prediction.SchedulingDecision,
					"estimated_wait_time":  prediction.EstimatedWaitTime,
					"confidence_score":     prediction.ConfidenceScore,
					"predicted_performance": prediction.PredictedPerf,
					"thermal_risk":         prediction.ThermalRisk,
					"memory_risk":          prediction.MemoryRisk,
					"resource_availability": prediction.ResourceAvailability,
				}

				// NEW: Check scheduling decision first
				if prediction.SchedulingDecision == "queue_short" || prediction.SchedulingDecision == "queue_long" {
					log.Printf("📋 AI recommends queuing job %s: %s (wait: %ds)",
						nextJob.ID, prediction.SchedulingReason, prediction.EstimatedWaitTime)

					// ENHANCED LOGGING: Job queued by AI
					logAIDecision(nextJob.ID, "QUEUE_DECISION", prediction.SchedulingReason, aiContext)
					logJobFlow(nextJob.ID, "AI_QUEUED", "AI recommends queuing job", map[string]interface{}{
						"decision":           prediction.SchedulingDecision,
						"wait_time_seconds":  prediction.EstimatedWaitTime,
						"reason":             prediction.SchedulingReason,
						"requesting_gpu":     gpuID,
					})

					// Don't assign the job yet - AI says to wait for better resource conditions
					w.Header().Set("Content-Type", "application/json")
					json.NewEncoder(w).Encode(map[string]interface{}{
						"job": nil,
						"message": fmt.Sprintf("job %s queued by AI scheduler: %s (estimated wait: %ds)",
							nextJob.ID, prediction.SchedulingReason, prediction.EstimatedWaitTime),
					})
					return
				}

				// If AI says assign_now, check if this GPU is the optimal one
				if prediction.BestGpuID != gpuID {
					log.Printf("🚫 AI recommends GPU %s over %s for job %s. Job stays in queue.", prediction.BestGpuID, gpuID, nextJob.ID)

					// ENHANCED LOGGING: GPU redirection
					logAIDecision(nextJob.ID, "GPU_REDIRECT", "AI recommends different GPU", aiContext)
					logJobFlow(nextJob.ID, "GPU_REDIRECT", "Job reserved for optimal GPU", map[string]interface{}{
						"requesting_gpu":  gpuID,
						"recommended_gpu": prediction.BestGpuID,
						"confidence":      prediction.ConfidenceScore,
					})

					// Don't assign this job to this GPU, let the optimal GPU poll for it
					w.Header().Set("Content-Type", "application/json")
					json.NewEncoder(w).Encode(map[string]interface{}{
						"job": nil,
						"message": fmt.Sprintf("job %s reserved for optimal GPU %s", nextJob.ID, prediction.BestGpuID),
					})
					return
				} else {
					log.Printf("✅ AI confirms GPU %s is optimal for job %s and ready for immediate assignment", gpuID, nextJob.ID)

					// ENHANCED LOGGING: AI approval for assignment
					logAIDecision(nextJob.ID, "ASSIGN_NOW", "AI approves immediate assignment", aiContext)
					logJobFlow(nextJob.ID, "AI_APPROVED", "AI approves assignment to requesting GPU", map[string]interface{}{
						"gpu_id":             gpuID,
						"confidence":         prediction.ConfidenceScore,
						"predicted_perf":     prediction.PredictedPerf,
						"scheduling_decision": prediction.SchedulingDecision,
					})
				}
			}
		}
	}

	// ATOMIC JOB ASSIGNMENT - Prevent race conditions
	jobAssignmentMux.Lock()
	defer jobAssignmentMux.Unlock()

	// Double-check job is still available after getting the lock
	queueMux.Lock()
	if len(jobQueue) == 0 || jobQueue[0].ID != nextJob.ID {
		queueMux.Unlock()
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"job": nil,
			"message": "job was assigned to another agent",
		})
		return
	}

	// Remove the job from queue now that we're assigning it
	jobQueue = jobQueue[1:]
	queueMux.Unlock()

	// NEW: Reserve resources immediately upon assignment
	reserveGpuResources(gpuID, nextJob)

	// Log resource usage after assignment
	clusterStateMux.RLock()
	if gpuState, exists := clusterState[gpuID]; exists {
		resourceSummary := getGpuResourceSummary(gpuID, gpuState)
		log.Printf("📊 Post-assignment resources for %s: %.0fMB/%.0fMB memory (%.1f%% projected), %.0f%% compute (%.1f%% projected)",
			gpuID, resourceSummary["current_memory_mb"], float64(gpuState.MemTotal),
			resourceSummary["projected_memory_mb"].(float64)/float64(gpuState.MemTotal)*100,
			resourceSummary["current_compute_pct"], resourceSummary["projected_compute_pct"])
	}
	clusterStateMux.RUnlock()

	log.Printf("📤 Polling agent %s assigned job: %s (resources reserved)", gpuID, nextJob.ID)

	// Convert to JobExecution format
	jobExecution := JobExecution{
		JobID:  nextJob.ID,
		Type:   nextJob.Type,
		Script: nextJob.Script,
		Args:   nextJob.Args,
		GpuID:  gpuID,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"job": jobExecution,
		"message": "job assigned",
	})
}

func main() {
	// Initialize comprehensive logging system
	if err := initLoggingSystem(); err != nil {
		log.Fatalf("Failed to initialize logging system: %v", err)
	}
	defer closeLoggingSystem()

	// Load job definitions
	if err := loadJobDefinitions(); err != nil {
		log.Printf("Warning: Failed to load job definitions: %v", err)
		log.Println("Job submission will be limited to basic job types")
	}

	// Connect to NATS
	nc, err := nats.Connect("0.tcp.in.ngrok.io:10968")
	if err != nil {
		log.Fatalf("Error connecting to NATS: %v", err)
	}
	defer nc.Close()

	// Set global NATS client
	natsClient = nc
	log.Println("Connected to NATS.")

	// Connect to TimescaleDB with connection pool
	dbUrl := "postgres://aether:aether@localhost:5432/aether"

	// Create connection pool configuration
	poolConfig, err := pgxpool.ParseConfig(dbUrl)
	if err != nil {
		log.Fatalf("Unable to parse database URL: %v", err)
	}

	// Configure pool for high-throughput telemetry
	poolConfig.MaxConns = 10         // Allow up to 10 concurrent connections
	poolConfig.MinConns = 2          // Keep 2 connections always open
	poolConfig.MaxConnLifetime = time.Hour
	poolConfig.MaxConnIdleTime = time.Minute * 30

	// Create the connection pool
	pool, err := pgxpool.ConnectConfig(context.Background(), poolConfig)
	if err != nil {
		log.Fatalf("Unable to create connection pool: %v", err)
	}
	dbPool = pool
	defer dbPool.Close()

	// Also create single connection for legacy compatibility
	conn, err := pgx.Connect(context.Background(), dbUrl)
	if err != nil {
		log.Fatalf("Unable to connect to database: %v", err)
	}
	dbConn = conn  // Set global connection
	defer dbConn.Close(context.Background())

	log.Println("Connected to TimescaleDB with connection pool (10 max connections).")

	// Subscribe to telemetry for all GPUs
	sub, err := nc.Subscribe("aether.telemetry.*", func(msg *nats.Msg) {
		var telemetry GpuTelemetry
		err := json.Unmarshal(msg.Data, &telemetry)
		if err != nil {
			log.Printf("Error decoding telemetry message: %v", err)
			return
		}

		// Use GPU ID from telemetry data (more reliable than parsing subject)
		gpuID := telemetry.GpuID
		if gpuID == "" {
			log.Printf("Warning: Telemetry missing gpu_id field, falling back to subject parsing")
			parts := strings.Split(msg.Subject, ".")
			gpuID = parts[len(parts)-1]
		}

		// CRITICAL FIX: Update cluster state IMMEDIATELY (non-blocking)
		// This ensures dashboard gets fresh data even if database is busy
		clusterStateMux.Lock()
		clusterState[gpuID] = GpuState{
			// Core telemetry
			GpuName:                     telemetry.GpuName,
			Temp:                        telemetry.TemperatureC,
			MemUsed:                     telemetry.MemoryUsedMb,
			MemTotal:                    telemetry.MemoryTotalMb,
			UtilizationGpu:              telemetry.UtilizationGpu,
			UtilizationMemoryController: telemetry.UtilizationMemoryController,
			PowerDrawW:                  telemetry.PowerDrawW,
			ThrottlingReasons:           telemetry.ThrottlingReasons,

			// Clock speeds
			ClockGpuMhz: telemetry.ClockGpuMhz,
			ClockMemMhz: telemetry.ClockMemMhz,

			// Performance state
			PerformanceState: telemetry.PerformanceState,

			// Telemetry tracking
			LastTelemetryUpdate: time.Now(),
		}
		clusterStateMux.Unlock()

		log.Printf("📊 Telemetry logged for %s (%s): Util=%d%%, Temp=%d°C, Mem=%d/%dMB",
			gpuID, telemetry.GpuName, telemetry.UtilizationGpu, telemetry.TemperatureC,
			telemetry.MemoryUsedMb, telemetry.MemoryTotalMb)

		// Insert telemetry data into database ASYNCHRONOUSLY to prevent blocking
		go func(tel GpuTelemetry, id string) {
			// Retry logic for database insertions using connection pool
			maxRetries := 3
			for attempt := 1; attempt <= maxRetries; attempt++ {
				_, err = dbPool.Exec(context.Background(),
					`INSERT INTO gpu_telemetry (
						time, gpu_id, gpu_name,
						utilization_gpu, utilization_memory_controller, performance_state,
						clock_gpu_mhz, clock_mem_mhz,
						memory_used_mb, memory_total_mb,
						temperature_c, power_draw_w, throttling_reasons
					) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)`,
					time.Now(),
					id,
					tel.GpuName,
					tel.UtilizationGpu,
					tel.UtilizationMemoryController,
					tel.PerformanceState,
					tel.ClockGpuMhz,
					tel.ClockMemMhz,
					tel.MemoryUsedMb,
					tel.MemoryTotalMb,
					tel.TemperatureC,
					tel.PowerDrawW,
					tel.ThrottlingReasons,
				)
				if err == nil {
					// Success - exit retry loop
					break
				}

				// Log error, but only spam log on final attempt
				if attempt == maxRetries {
					log.Printf("❌ Failed to insert telemetry for %s after %d attempts: %v", id, maxRetries, err)
				} else if attempt == 1 {
					// Log first failure at debug level
					log.Printf("⚠️ Telemetry insert attempt %d failed for %s (retrying): %v", attempt, id, err)
				}

				// Brief delay before retry to let database settle
				time.Sleep(time.Duration(attempt*50) * time.Millisecond)
			}
		}(telemetry, gpuID)
	})
	if err != nil {
		log.Fatalf("Error subscribing to NATS: %v", err)
	}
	defer sub.Unsubscribe()

	// Subscribe to job status updates
	statusSub, err := nc.Subscribe("aether.status.*", func(msg *nats.Msg) {
		// Parse job status update
		var status JobStatus
		if err := json.Unmarshal(msg.Data, &status); err != nil {
			log.Printf("Error decoding job status: %v", err)
			return
		}

		// Update job status
		jobStatusMux.Lock()
		activeJobStatus[status.JobID] = status
		jobStatusMux.Unlock()

		log.Printf("📊 Job status update: %s - %s (%s)", status.JobID, status.Status, status.Message)

		// NEW: Resource tracking based on job status changes
		gpuID := status.GpuID
		jobID := status.JobID

		switch status.Status {
		case "running":
			// Job started running - move from pending to running
			moveJobToPendingToRunning(gpuID, jobID)

		case "completed", "failed", "killed":
			// Job finished - release all resources
			releaseGpuResources(gpuID, jobID)

			// Log current resource state after release
			clusterStateMux.RLock()
			if gpuState, exists := clusterState[gpuID]; exists {
				resourceSummary := getGpuResourceSummary(gpuID, gpuState)
				log.Printf("📊 Post-completion resources for %s: %.0f pending jobs, %.0f running jobs, %.0fMB available memory",
					gpuID, resourceSummary["pending_jobs"], resourceSummary["running_jobs"], resourceSummary["memory_available_mb"])
			}
			clusterStateMux.RUnlock()
		}

		// Move completed/failed jobs to completed jobs list
		if status.Status == "completed" || status.Status == "failed" || status.Status == "killed" {
			// Store job performance data for AI training
			go func(completedStatus JobStatus) {
				if err := storeJobPerformanceData(completedStatus); err != nil {
					log.Printf("❌ Error storing job performance data for %s: %v", completedStatus.JobID, err)
				} else {
					log.Printf("💾 Stored performance data for job %s", completedStatus.JobID)
				}
			}(status)

			// Add to completed jobs list (keep only last 10)
			if len(completedJobs) >= 10 {
				completedJobs = completedJobs[1:] // Remove oldest
			}
			completedJobs = append(completedJobs, status)

			// Clean up from active jobs after 15 seconds to give UI time to show completion
			go func(jobID string) {
				time.Sleep(15 * time.Second)
				jobStatusMux.Lock()
				delete(activeJobStatus, jobID)
				jobStatusMux.Unlock()
				log.Printf("🧹 Moved job %s from active to completed", jobID)
			}(status.JobID)
		}
	})
	if err != nil {
		log.Fatalf("Error subscribing to job status: %v", err)
	}
	defer statusSub.Unsubscribe()

	// Start the HTTP server in a separate goroutine
	go func() {
		// Handle OPTIONS requests for CORS preflight
		http.HandleFunc("/submit", func(w http.ResponseWriter, r *http.Request) {
			if r.Method == "OPTIONS" {
				corsHandler(w, r)
				return
			}
			corsMiddleware(handleSubmit)(w, r)
		})
		http.HandleFunc("/kill/", func(w http.ResponseWriter, r *http.Request) {
			if r.Method == "OPTIONS" {
				corsHandler(w, r)
				return
			}
			corsMiddleware(handleKill)(w, r)
		})
		http.HandleFunc("/poll", func(w http.ResponseWriter, r *http.Request) {
			if r.Method == "OPTIONS" {
				corsHandler(w, r)
				return
			}
			corsMiddleware(handlePoll)(w, r)
		})
		http.HandleFunc("/graphql", graphqlHandler) // Add the WebSocket handler
		log.Println("API server listening on :8080")
		if err := http.ListenAndServe(":8080", nil); err != nil {
			log.Fatalf("Error starting API server: %v", err)
		}
	}()

	// Start the main scheduling loop
	// go scheduleJobs() // Disabled: conflicts with HTTP polling system

	log.Println("Orchestrator started. Now processing jobs.")
	// Keep the NATS subscription running
	select {} // Block forever
}
