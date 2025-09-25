package scheduler

import (
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/nats-io/nats.go"
)

// GangJob represents a multi-GPU job that requires coordinated execution
type GangJob struct {
	ID                   string                 `json:"id"`
	RequiredGPUs         []string               `json:"required_gpus"`
	GPUCount             int                    `json:"gpu_count"`
	GangID               string                 `json:"gang_id"`
	CoordinationRequired bool                   `json:"coordination_required"`
	CheckpointInterval   int                    `json:"checkpoint_interval"`
	Priority             int                    `json:"priority"`
	CreatedAt            time.Time              `json:"created_at"`
	Status               string                 `json:"status"`
	Metadata             map[string]interface{} `json:"metadata"`
}

// GangCommand represents commands sent to GPU agents for gang coordination
type GangCommand struct {
	Type      string                 `json:"type"`
	GangID    string                 `json:"gang_id"`
	JobID     string                 `json:"job_id"`
	GPUIDs    []string               `json:"gpu_ids"`
	Data      map[string]interface{} `json:"data"`
	Timestamp time.Time              `json:"timestamp"`
}

// GangScheduler manages multi-GPU job coordination
type GangScheduler struct {
	ActiveGangs          map[string]*GangJob           `json:"active_gangs"`
	GangQueues           map[int][]*GangJob            `json:"gang_queues"`
	ResourceReservations map[string][]string           `json:"resource_reservations"`
	AllocationLock       sync.RWMutex                  `json:"-"`
	NATSClient           *nats.Conn                    `json:"-"`
	CheckpointManager    *CheckpointManager            `json:"-"`
}

// CheckpointManager handles job state checkpointing for preemption
type CheckpointManager struct {
	Checkpoints map[string]*JobCheckpoint `json:"checkpoints"`
	Lock        sync.RWMutex              `json:"-"`
}

// JobCheckpoint represents a saved job state
type JobCheckpoint struct {
	JobID       string                 `json:"job_id"`
	GangID      string                 `json:"gang_id"`
	State       map[string]interface{} `json:"state"`
	CreatedAt   time.Time              `json:"created_at"`
	IsValid     bool                   `json:"is_valid"`
}

// NewGangScheduler creates a new gang scheduler instance
func NewGangScheduler(nc *nats.Conn) *GangScheduler {
	return &GangScheduler{
		ActiveGangs:          make(map[string]*GangJob),
		GangQueues:           make(map[int][]*GangJob),
		ResourceReservations: make(map[string][]string),
		NATSClient:           nc,
		CheckpointManager: &CheckpointManager{
			Checkpoints: make(map[string]*JobCheckpoint),
		},
	}
}

// SubmitGangJob adds a new gang job to the appropriate priority queue
func (gs *GangScheduler) SubmitGangJob(job *GangJob) error {
	gs.AllocationLock.Lock()
	defer gs.AllocationLock.Unlock()

	// Validate gang job
	if err := gs.validateGangJob(job); err != nil {
		return fmt.Errorf("invalid gang job: 