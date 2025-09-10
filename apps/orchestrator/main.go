package main

import (
	"bytes"
	"context"
	"encoding/json"
	"log"
	"net/http"
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
	ID   string `json:"id"`
	Type string `json:"type"` // e.g., "training" or "inference"
}

// Represents the current state of a GPU, which we'll send to the AI
type GpuState struct {
	Temp              uint32 `json:"gpu_temp"`
	MemUsed           uint64 `json:"gpu_mem_used"`
	UtilizationGpu    uint32 `json:"utilization_gpu"`
	PowerDrawW        uint32 `json:"power_draw_w"`
	ThrottlingReasons string `json:"throttling_reasons"`
}

// Candidate sent to AI Core with ID
type GpuCandidate struct {
	GpuID             string `json:"gpu_id"`
	Temp              uint32 `json:"gpu_temp"`
	MemUsed           uint64 `json:"gpu_mem_used"`
	UtilizationGpu    uint32 `json:"utilization_gpu"`
	PowerDrawW        uint32 `json:"power_draw_w"`
	ThrottlingReasons string `json:"throttling_reasons"`
}

// PredictionRequest matches the Python API's expected input
type PredictionRequest struct {
	Candidates []GpuCandidate `json:"candidates"`
	JobType    string         `json:"job_type"`
}

// PredictionResponse matches the Python API's output
type PredictionResponse struct {
	BestGpuID string `json:"best_gpu_id"`
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

// askAICoreCandidates sends all GPU candidates to the AI service and gets the best GPU ID
func askAICoreCandidates(cluster map[string]GpuState, job Job) (string, error) {
	aiCoreURL := "http://localhost:8000/predict"

	candidates := make([]GpuCandidate, 0, len(cluster))
	for id, s := range cluster {
		candidates = append(candidates, GpuCandidate{
			GpuID:             id,
			Temp:              s.Temp,
			MemUsed:           s.MemUsed,
			UtilizationGpu:    s.UtilizationGpu,
			PowerDrawW:        s.PowerDrawW,
			ThrottlingReasons: s.ThrottlingReasons,
		})
	}

	requestBody, err := json.Marshal(PredictionRequest{
		Candidates: candidates,
		JobType:    job.Type,
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

	return predictionResp.BestGpuID, nil
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

		// Update the cluster state for this GPU
		clusterStateMux.Lock()
		clusterState[gpuID] = GpuState{
			Temp:              telemetry.TemperatureC,
			MemUsed:           telemetry.MemoryUsedMb,
			UtilizationGpu:    telemetry.UtilizationGpu,
			PowerDrawW:        telemetry.PowerDrawW,
			ThrottlingReasons: telemetry.ThrottlingReasons,
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
		http.HandleFunc("/submit", handleSubmit)
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
