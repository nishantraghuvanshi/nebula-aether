package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	"github.com/jackc/pgx/v4"
	"github.com/nats-io/nats.go"
)

// This struct must match the Rust agent's enhanced GpuTelemetry struct
type GpuTelemetry struct {
	// === EXISTING FIELDS (unchanged for backward compatibility) ===
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

	// === NEW OPTIONAL FIELDS (from enhanced Rust agent) ===
	// These fields may be null/nil if not provided by older agent versions
	GpuVendor              *string `json:"gpu_vendor"`               // "NVIDIA", "AMD", "Intel", "Apple"
	GpuArchitecture        *string `json:"gpu_architecture"`         // "Ada Lovelace", "RDNA3", etc.
	UtilizationEncoder     *uint32 `json:"utilization_encoder"`      // Video encoder utilization %
	UtilizationDecoder     *uint32 `json:"utilization_decoder"`      // Video decoder utilization %
	PcieTxThroughputMbps   *uint32 `json:"pcie_tx_throughput_mbps"`  // PCIe transmit MB/s
	PcieRxThroughputMbps   *uint32 `json:"pcie_rx_throughput_mbps"`  // PCIe receive MB/s
	EccErrorsCorrectable   *uint32 `json:"ecc_errors_correctable"`   // Correctable ECC errors
	EccErrorsUncorrectable *uint32 `json:"ecc_errors_uncorrectable"` // Uncorrectable ECC errors
}

// Job struct to define a workload with enhanced requirements
type Job struct {
	ID   string `json:"id"`
	Type string `json:"type"` // e.g., "training" or "inference"
	// === NEW HARD CONSTRAINTS ===
	VramRequiredMB uint64 `json:"vram_required_mb"` // VRAM requirement in MB
	GpuCount       int    `json:"gpu_count"`        // Number of GPUs required (default: 1)
	Priority       int    `json:"priority"`         // Job priority (0-10, higher = more important)
	// === NEW SOFT HINTS ===
	UserID           string `json:"user_id"`           // User submitting the job
	TenantID         string `json:"tenant_id"`         // Tenant/organization ID
	ExpectedDuration string `json:"expected_duration"` // "short", "medium", "long"
	ComputeIntensity string `json:"compute_intensity"` // "compute-bound", "memory-bound", "io-bound"
}

// Represents the current state of a GPU, which we'll send to the AI
type GpuState struct {
	Temp              uint32 `json:"gpu_temp"`
	MemUsed           uint64 `json:"gpu_mem_used"`
	MemTotal          uint64 `json:"gpu_mem_total"` // NEW: Total VRAM for constraint checking
	UtilizationGpu    uint32 `json:"utilization_gpu"`
	PowerDrawW        uint32 `json:"power_draw_w"`
	ThrottlingReasons string `json:"throttling_reasons"`
	GpuName           string `json:"gpu_name"`
	// === NEW ENHANCED FIELDS ===
	GpuVendor       string `json:"gpu_vendor"`       // "NVIDIA", "AMD", "Intel", "Apple"
	GpuArchitecture string `json:"gpu_architecture"` // "Ada Lovelace", "RDNA3", etc.
}

// Candidate sent to AI Core with ID and enhanced information
type GpuCandidate struct {
	GpuID             string `json:"gpu_id"`
	Temp              uint32 `json:"gpu_temp"`
	MemUsed           uint64 `json:"gpu_mem_used"`
	MemTotal          uint64 `json:"gpu_mem_total"` // NEW: Total VRAM for AI decision making
	UtilizationGpu    uint32 `json:"utilization_gpu"`
	PowerDrawW        uint32 `json:"power_draw_w"`
	ThrottlingReasons string `json:"throttling_reasons"`
	// === NEW ENHANCED FIELDS ===
	GpuVendor       string `json:"gpu_vendor"`       // GPU vendor for vendor-aware scheduling
	GpuArchitecture string `json:"gpu_architecture"` // GPU architecture for performance estimation
}

// PredictionRequest matches the Python AI Core's expected input with enhanced job context
type PredictionRequest struct {
	Candidates []GpuCandidate `json:"candidates"`
	JobType    string         `json:"job_type"`
	// === NEW JOB CONTEXT ===
	VramRequiredMB   uint64 `json:"vram_required_mb"`  // VRAM requirement for constraint checking
	GpuCount         int    `json:"gpu_count"`         // Number of GPUs needed
	Priority         int    `json:"priority"`          // Job priority for scheduling decisions
	UserID           string `json:"user_id"`           // User context for fairness
	TenantID         string `json:"tenant_id"`         // Tenant context for resource allocation
	ExpectedDuration string `json:"expected_duration"` // Duration hint for scheduling
	ComputeIntensity string `json:"compute_intensity"` // Workload type hint
}

// PredictionResponse matches the Python AI Core's output with enhanced decision context
type PredictionResponse struct {
	BestGpuIDs    []string `json:"best_gpu_ids"`   // Selected GPU IDs (supports multi-GPU)
	Confidence    float64  `json:"confidence"`     // Confidence score (0.0-1.0)
	ReasonCode    string   `json:"reason_code"`    // Human-readable decision reason
	FailureReason string   `json:"failure_reason"` // Why placement failed (if any)
}

// DashboardUpdate packages full cluster info for the dashboard
type DashboardUpdate struct {
	ClusterState    map[string]GpuState `json:"cluster_state"`
	CarbonIntensity float64             `json:"carbon_intensity"`
	Anomalies       map[string]bool     `json:"anomalies"`
}

// mockCarbonIntensity returns a placeholder carbon intensity value
func mockCarbonIntensity() float64 {
	// Simple oscillating mock between 100-500
	return 100 + float64(time.Now().Unix()%400)
}

// getStringField safely extracts string from pointer with default fallback
func getStringField(field *string, defaultValue string) string {
	if field != nil {
		return *field
	}
	return defaultValue
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
)

// filterViableGpus applies hard constraints to filter out GPUs that cannot satisfy the job requirements
func filterViableGpus(clusterState map[string]GpuState, job Job) ([]GpuCandidate, error) {
	var viableCandidates []GpuCandidate

	// Validate job requirements
	if job.VramRequiredMB == 0 {
		// Default VRAM requirement based on job type if not specified
		switch job.Type {
		case "training":
			job.VramRequiredMB = 4096 // 4GB default for training
		case "inference":
			job.VramRequiredMB = 2048 // 2GB default for inference
		default:
			job.VramRequiredMB = 1024 // 1GB default for unknown job types
		}
		log.Printf("No VRAM requirement specified for job %s, using default: %d MB", job.ID, job.VramRequiredMB)
	}

	if job.GpuCount == 0 {
		job.GpuCount = 1 // Default to single GPU
	}

	log.Printf("Filtering GPUs for job %s: VRAM needed=%d MB, GPU count=%d",
		job.ID, job.VramRequiredMB, job.GpuCount)

	for gpuID, state := range clusterState {
		// HARD CONSTRAINT 1: Available VRAM check
		availableMemory := state.MemTotal - state.MemUsed
		if availableMemory < job.VramRequiredMB {
			log.Printf("GPU %s rejected: insufficient VRAM (available: %d MB, needed: %d MB)",
				gpuID, availableMemory, job.VramRequiredMB)
			continue
		}

		// HARD CONSTRAINT 2: GPU health check
		if state.ThrottlingReasons != "" && state.ThrottlingReasons != "None" && state.ThrottlingReasons != "[]" {
			log.Printf("GPU %s rejected: throttling active (%s)", gpuID, state.ThrottlingReasons)
			continue
		}

		// HARD CONSTRAINT 3: Temperature safety check
		if state.Temp >= 90 {
			log.Printf("GPU %s rejected: temperature too high (%d°C)", gpuID, state.Temp)
			continue
		}

		// GPU passes all hard constraints
		viableCandidates = append(viableCandidates, GpuCandidate{
			GpuID:             gpuID,
			Temp:              state.Temp,
			MemUsed:           state.MemUsed,
			MemTotal:          state.MemTotal,
			UtilizationGpu:    state.UtilizationGpu,
			PowerDrawW:        state.PowerDrawW,
			ThrottlingReasons: state.ThrottlingReasons,
			GpuVendor:         state.GpuVendor,
			GpuArchitecture:   state.GpuArchitecture,
		})

		log.Printf("GPU %s viable: %d MB available, %d°C, %d%% utilization",
			gpuID, availableMemory, state.Temp, state.UtilizationGpu)
	}

	// Check if we have enough viable GPUs
	if len(viableCandidates) < job.GpuCount {
		return nil, fmt.Errorf("insufficient viable GPUs: need %d, found %d", job.GpuCount, len(viableCandidates))
	}

	log.Printf("Pre-filtering complete: %d viable candidates for job %s", len(viableCandidates), job.ID)
	return viableCandidates, nil
}

// askAICoreCandidates sends viable GPU candidates to the AI service and gets the best GPU ID
func askAICoreCandidates(cluster map[string]GpuState, job Job) (string, error) {
	aiCoreURL := "http://localhost:8000/predict"

	// Use pre-filtering to get viable candidates
	viableCandidates, err := filterViableGpus(cluster, job)
	if err != nil {
		return "", fmt.Errorf("pre-filtering failed: %v", err)
	}

	// Create enhanced prediction request with job context
	requestBody, err := json.Marshal(PredictionRequest{
		Candidates:       viableCandidates,
		JobType:          job.Type,
		VramRequiredMB:   job.VramRequiredMB,
		GpuCount:         job.GpuCount,
		Priority:         job.Priority,
		UserID:           job.UserID,
		TenantID:         job.TenantID,
		ExpectedDuration: job.ExpectedDuration,
		ComputeIntensity: job.ComputeIntensity,
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

	// Handle the new response format - return first GPU ID for backward compatibility
	if len(predictionResp.BestGpuIDs) == 0 {
		return "", fmt.Errorf("AI Core returned no GPU recommendations: %s", predictionResp.FailureReason)
	}
	return predictionResp.BestGpuIDs[0], nil
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

		// Get the most recent GPU state for scheduling decision
		clusterStateMux.RLock()
		clusterSnapshot := make(map[string]GpuState, len(clusterState))
		for gpuID, state := range clusterState {
			clusterSnapshot[gpuID] = state
		}
		clusterStateMux.RUnlock()

		log.Printf("Attempting to schedule job %s (type: %s, VRAM: %d MB, priority: %d)",
			jobToSchedule.ID, jobToSchedule.Type, jobToSchedule.VramRequiredMB, jobToSchedule.Priority)

		// Ask the AI for a decision (includes pre-filtering)
		bestGpuID, err := askAICoreCandidates(clusterSnapshot, jobToSchedule)
		if err != nil {
			log.Printf("Error consulting AI core: %v. Re-queuing job.", err)
			// In a real system, you'd add the job back to the queue with better logic
			continue
		}

		log.Printf("AI approved! Scheduling job %s on GPU %s.", jobToSchedule.ID, bestGpuID)
		// In the future, this is where we would publish a command to NATS
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
		update := DashboardUpdate{
			ClusterState:    snapshot,
			CarbonIntensity: mockCarbonIntensity(),
			Anomalies:       checkAllAnomalies(snapshot),
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

	var job Job
	if err := json.NewDecoder(r.Body).Decode(&job); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	// Validate required fields
	if job.ID == "" {
		http.Error(w, "Job ID is required", http.StatusBadRequest)
		return
	}
	if job.Type == "" {
		http.Error(w, "Job Type is required", http.StatusBadRequest)
		return
	}

	// Validate job type
	if job.Type != "training" && job.Type != "inference" {
		http.Error(w, "Job Type must be 'training' or 'inference'", http.StatusBadRequest)
		return
	}

	queueMux.Lock()
	jobQueue = append(jobQueue, job)
	queueMux.Unlock()

	log.Printf("Added job to queue: ID=%s, Type=%s", job.ID, job.Type)
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]string{"status": "job added"})
}

func main() {
	// Connect to NATS
	nc, err := nats.Connect("nats://localhost:4222")
	if err != nil {
		log.Fatalf("Error connecting to NATS: %v", err)
	}
	defer nc.Close()
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

		// Update the cluster state for this GPU with enhanced fields
		clusterStateMux.Lock()
		clusterState[gpuID] = GpuState{
			Temp:              telemetry.TemperatureC,
			MemUsed:           telemetry.MemoryUsedMb,
			MemTotal:          telemetry.MemoryTotalMb, // NEW: Total memory for constraint checking
			UtilizationGpu:    telemetry.UtilizationGpu,
			PowerDrawW:        telemetry.PowerDrawW,
			ThrottlingReasons: telemetry.ThrottlingReasons,
			GpuName:           telemetry.GpuName,
			// NEW: Enhanced vendor and architecture information
			GpuVendor:       getStringField(telemetry.GpuVendor, "Unknown"),
			GpuArchitecture: getStringField(telemetry.GpuArchitecture, "Unknown"),
		}
		clusterStateMux.Unlock()

		log.Printf("Logged telemetry for %s on %s", telemetry.GpuName, gpuID)
	})
	if err != nil {
		log.Fatalf("Error subscribing to NATS: %v", err)
	}
	defer sub.Unsubscribe()

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
