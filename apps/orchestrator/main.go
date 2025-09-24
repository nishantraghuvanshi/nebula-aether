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
	"github.com/nats-io/nats.go"
)

// This struct must match the Rust agent's GpuTelemetry struct
type GpuTelemetry struct {
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

// JobStatus struct for receiving status updates
type JobStatus struct {
	JobID     string `json:"job_id"`
	GpuID     string `json:"gpu_id"`
	Status    string `json:"status"` // "started", "running", "completed", "failed"
	Message   string `json:"message"`
	StartTime *int64 `json:"start_time,omitempty"`
	EndTime   *int64 `json:"end_time,omitempty"`
	ExitCode  *int   `json:"exit_code,omitempty"`
}

// Represents the current state of a GPU, which we'll send to the AI
type GpuState struct {
	// Core telemetry
	GpuName                     string `json:"gpu_name"`
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

// Enhanced PredictionResponse
type PredictionResponse struct {
	BestGpuID           string    `json:"best_gpu_id"`
	ConfidenceScore     float64   `json:"confidence_score"`
	PredictedPerf       float64   `json:"predicted_performance"`
	ThermalRisk         float64   `json:"thermal_risk"`
	MemoryRisk          float64   `json:"memory_risk"`
	Reasons             []string  `json:"reasons"`
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
	jobDefinitions  = make(map[string]Job)        // Job definitions by ID
	activeJobStatus = make(map[string]JobStatus)  // Current job status by job ID
	completedJobs   = make([]JobStatus, 0)        // Recently completed jobs
	jobStatusMux    = &sync.RWMutex{}
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

// askAICoreCandidates sends all GPU candidates to the AI service and gets the best GPU ID
func askAICoreCandidates(cluster map[string]GpuState, job Job) (string, error) {
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

	// Get the next job from the queue
	job := jobQueue[0]
	jobQueue = jobQueue[1:]
	queueMux.Unlock()

	log.Printf("📤 Polling agent %s retrieved job: %s", gpuID, job.ID)

	// Convert to JobExecution format
	jobExecution := JobExecution{
		JobID:  job.ID,
		Type:   job.Type,
		Script: job.Script,
		Args:   job.Args,
		GpuID:  gpuID,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"job": jobExecution,
		"message": "job assigned",
	})
}

func main() {
	// Load job definitions
	if err := loadJobDefinitions(); err != nil {
		log.Printf("Warning: Failed to load job definitions: %v", err)
		log.Println("Job submission will be limited to basic job types")
	}

	// Connect to NATS
	nc, err := nats.Connect("nats://0.tcp.in.ngrok.io:16521")
	if err != nil {
		log.Fatalf("Error connecting to NATS: %v", err)
	}
	defer nc.Close()

	// Set global NATS client
	natsClient = nc
	log.Println("Connected to NATS.")

	// Connect to TimescaleDB
	dbUrl := "postgres://aether:aether@localhost:5432/aether"
	conn, err := pgx.Connect(context.Background(), dbUrl)
	if err != nil {
		log.Fatalf("Unable to connect to database: %v", err)
	}
	defer conn.Close(context.Background())
	log.Println("Connected to TimescaleDB.")

	// Subscribe to telemetry for all GPUs
	sub, err := nc.Subscribe("aether.telemetry.*", func(msg *nats.Msg) {
		// Example subject: aether.telemetry.gpu-0
		parts := strings.Split(msg.Subject, ".")
		gpuID := parts[len(parts)-1]
		var telemetry GpuTelemetry
		err := json.Unmarshal(msg.Data, &telemetry)
		if err != nil {
			log.Printf("Error decoding message: %v", err)
			return
		}

		// Insert the data into the database
		_, err = conn.Exec(context.Background(),
			`INSERT INTO gpu_telemetry (time, gpu_name, temperature_c, memory_used_mb, memory_total_mb, 
			utilization_gpu, utilization_memory_controller, power_draw_w, clock_gpu_mhz, clock_mem_mhz, 
			performance_state, throttling_reasons, gpu_id) 
			VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)`,
			time.Now(),
			telemetry.GpuName,
			telemetry.TemperatureC,
			telemetry.MemoryUsedMb,
			telemetry.MemoryTotalMb,
			telemetry.UtilizationGpu,
			telemetry.UtilizationMemoryController,
			telemetry.PowerDrawW,
			telemetry.ClockGpuMhz,
			telemetry.ClockMemMhz,
			telemetry.PerformanceState,
			telemetry.ThrottlingReasons,
			gpuID,
		)
		if err != nil {
			log.Printf("Error inserting data: %v", err)
			return
		}

		// Update the cluster state for this GPU with all telemetry fields
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
		}
		clusterStateMux.Unlock()

		log.Printf("Logged telemetry for %s on %s", telemetry.GpuName, gpuID)
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

		// Move completed/failed jobs to completed jobs list
		if status.Status == "completed" || status.Status == "failed" || status.Status == "killed" {
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
	go scheduleJobs()

	log.Println("Orchestrator started. Now processing jobs.")
	// Keep the NATS subscription running
	select {} // Block forever
}
