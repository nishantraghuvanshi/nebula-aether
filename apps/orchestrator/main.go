package main

import (
	"bytes"
	"context"
	"encoding/json"
	"log"
	"math/rand"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	"github.com/jackc/pgx/v4"
	"github.com/nats-io/nats.go"
)

// This struct must match the Rust agent's GpuTelemetry struct
type GpuTelemetry struct {
	GpuName       string `json:"gpu_name"`
	TemperatureC  uint32 `json:"temperature_c"`
	MemoryUsedMb  uint64 `json:"memory_used_mb"`
	MemoryTotalMb uint64 `json:"memory_total_mb"`
}

// Job struct to define a workload
type Job struct {
	ID   string `json:"id"`
	Type string `json:"type"` // e.g., "training" or "inference"
}

// Represents the current state of a GPU, which we'll send to the AI
type GpuState struct {
	Temp    uint32 `json:"gpu_temp"`
	MemUsed uint64 `json:"gpu_mem_used"`
}

// PredictionRequest matches the Python API's expected input
type PredictionRequest struct {
	GpuTemp         uint32  `json:"gpu_temp"`
	GpuMemUsed      uint64  `json:"gpu_mem_used"`
	JobType         string  `json:"job_type"`
	CarbonIntensity float64 `json:"carbon_intensity"`
}

// PredictionResponse matches the Python API's output
type PredictionResponse struct {
	IsGoodPlacement bool   `json:"is_good_placement"`
	Reason          string `json:"reason"`
}

// WebSocket upgrader for dashboard connections
var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin:     func(r *http.Request) bool { return true }, // Allow all origins for dev
}

// Global variables to hold the current state
var (
	jobQueue       = make([]Job, 0)
	queueMux       = &sync.Mutex{}
	latestGpuState = GpuState{}
	gpuStateMux    = &sync.RWMutex{}
)

// askAICore sends the current state to the Python AI service and gets a recommendation
func askAICore(gpuState GpuState, job Job) (bool, string, error) {
	// The URL of our Python AI service
	aiCoreURL := "http://localhost:8000/predict"

	// Mock carbon intensity data
	mockCarbonIntensity := float64(rand.Intn(600)) // Random value between 0-599
	log.Printf("Mock carbon intensity: %.2f gCO2eq/kWh", mockCarbonIntensity)

	requestBody, err := json.Marshal(PredictionRequest{
		GpuTemp:         gpuState.Temp,
		GpuMemUsed:      gpuState.MemUsed,
		JobType:         job.Type,
		CarbonIntensity: mockCarbonIntensity,
	})
	if err != nil {
		return false, "", err
	}

	resp, err := http.Post(aiCoreURL, "application/json", bytes.NewBuffer(requestBody))
	if err != nil {
		return false, "", err
	}
	defer resp.Body.Close()

	var predictionResp PredictionResponse
	if err := json.NewDecoder(resp.Body).Decode(&predictionResp); err != nil {
		return false, "", err
	}

	return predictionResp.IsGoodPlacement, predictionResp.Reason, nil
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
		gpuStateMux.RLock()
		currentGpuState := latestGpuState
		gpuStateMux.RUnlock()

		log.Printf("Attempting to schedule job %s. Current GPU state: Temp=%dC, MemUsed=%dMB",
			jobToSchedule.ID, currentGpuState.Temp, currentGpuState.MemUsed)

		// Ask the AI for a decision
		isGoodPlacement, reason, err := askAICore(currentGpuState, jobToSchedule)
		if err != nil {
			log.Printf("Error consulting AI core: %v. Re-queuing job.", err)
			// In a real system, you'd add the job back to the queue with better logic
			continue
		}

		if isGoodPlacement {
			log.Printf("AI approved! Scheduling job %s on GPU. Reason: %s", jobToSchedule.ID, reason)
			// In the future, this is where we would publish a command to NATS
		} else {
			log.Printf("AI denied. Reason: %s. Re-queuing job.", reason)
			// Re-queue the job for a later attempt
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

	// Periodically send the latest GPU state to the dashboard
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		gpuStateMux.RLock()
		currentState := latestGpuState
		gpuStateMux.RUnlock()

		// Marshal the state into JSON to send over WebSocket
		payload, _ := json.Marshal(currentState)

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

	// Subscribe to the telemetry topic
	sub, err := nc.Subscribe("aether.telemetry.gpu-0", func(msg *nats.Msg) {
		var telemetry GpuTelemetry
		err := json.Unmarshal(msg.Data, &telemetry)
		if err != nil {
			log.Printf("Error decoding message: %v", err)
			return
		}

		// Insert the data into the database
		_, err = conn.Exec(context.Background(),
			"INSERT INTO gpu_telemetry (time, gpu_name, temperature_c, memory_used_mb, memory_total_mb) VALUES ($1, $2, $3, $4, $5)",
			time.Now(),
			telemetry.GpuName,
			telemetry.TemperatureC,
			telemetry.MemoryUsedMb,
			telemetry.MemoryTotalMb,
		)
		if err != nil {
			log.Printf("Error inserting data: %v", err)
			return
		}

		// Update the global state
		gpuStateMux.Lock()
		latestGpuState = GpuState{
			Temp:    telemetry.TemperatureC,
			MemUsed: telemetry.MemoryUsedMb,
		}
		gpuStateMux.Unlock()

		// Anomaly detection in a separate goroutine
		go func(tel GpuTelemetry) {
			reqBody, _ := json.Marshal(map[string]interface{}{
				"gpu_temp":     tel.TemperatureC,
				"gpu_mem_used": tel.MemoryUsedMb,
			})

			resp, err := http.Post("http://localhost:8000/anomaly", "application/json", bytes.NewBuffer(reqBody))
			if err != nil {
				log.Printf("Error checking anomaly: %v", err)
				return
			}
			defer resp.Body.Close()

			var anomalyResp map[string]bool
			if err := json.NewDecoder(resp.Body).Decode(&anomalyResp); err != nil {
				log.Printf("Error decoding anomaly response: %v", err)
				return
			}

			if anomalyResp["is_anomaly"] {
				log.Printf("🚨 ANOMALY DETECTED! GPU: %s, Temp: %d°C, Memory: %dMB", tel.GpuName, tel.TemperatureC, tel.MemoryUsedMb)
			}
		}(telemetry)

		log.Printf("Logged telemetry for: %s", telemetry.GpuName)
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
