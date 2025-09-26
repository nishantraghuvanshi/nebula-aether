-- Enhanced GPU telemetry table to match Rust agent telemetry data
CREATE TABLE gpu_telemetry (
    time TIMESTAMPTZ NOT NULL,

    -- GPU Identification
    gpu_id TEXT NOT NULL,
    gpu_name TEXT,

    -- Performance & Utilization
    utilization_gpu INTEGER,
    utilization_memory_controller INTEGER,
    performance_state TEXT,
    clock_gpu_mhz INTEGER,
    clock_mem_mhz INTEGER,

    -- Memory Information
    memory_used_mb BIGINT,
    memory_total_mb BIGINT,

    -- Thermal & Power
    temperature_c INTEGER,
    power_draw_w INTEGER,
    throttling_reasons TEXT
);

-- Create hypertable for time-series data
SELECT create_hypertable('gpu_telemetry', 'time');

-- Create indexes for common queries
CREATE INDEX idx_gpu_telemetry_gpu_id ON gpu_telemetry (gpu_id, time DESC);
CREATE INDEX idx_gpu_telemetry_utilization ON gpu_telemetry (utilization_gpu, time DESC);
CREATE INDEX idx_gpu_telemetry_temperature ON gpu_telemetry (temperature_c, time DESC);

-- ================================
-- DUAL-MODE AI LEARNING SYSTEM TABLES
-- ================================

-- Job performance tracking for AI model training
CREATE TABLE job_performance (
    id SERIAL PRIMARY KEY,
    job_id TEXT NOT NULL,
    gpu_id TEXT NOT NULL,
    job_type TEXT NOT NULL,

    -- Job Context
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    duration_seconds INTEGER,
    exit_code INTEGER,

    -- Performance Metrics (extracted from job output)
    throughput REAL,                    -- Job-specific throughput (samples/sec, frames/sec, etc.)
    completion_time_sec REAL,           -- Actual time to complete workload
    samples_per_second REAL,            -- Processing rate
    memory_efficiency REAL,             -- Memory utilization efficiency (0-1)
    computational_efficiency REAL,      -- GPU compute utilization efficiency (0-1)

    -- Resource Correlation (average during job execution)
    avg_gpu_utilization REAL,          -- Average GPU utilization during job
    max_gpu_utilization REAL,          -- Peak GPU utilization
    avg_memory_utilization REAL,       -- Average memory usage
    max_memory_usage_mb BIGINT,         -- Peak memory usage
    avg_temperature INTEGER,            -- Average temperature during job
    max_temperature INTEGER,            -- Peak temperature reached
    avg_power_draw REAL,                -- Average power consumption
    thermal_events INTEGER,             -- Number of thermal throttling events

    -- AI Training Labels (computed metrics)
    performance_score REAL,            -- Overall performance score (0-100)
    resource_efficiency REAL,          -- Resource utilization efficiency (0-1)
    thermal_impact REAL,               -- Thermal impact score (0-1, lower is better)
    power_efficiency REAL,             -- Performance per watt
    reliability_score REAL,            -- Job completion reliability (0-1)

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Model performance and accuracy tracking
CREATE TABLE model_performance (
    id SERIAL PRIMARY KEY,
    model_name TEXT NOT NULL,           -- e.g., 'training_v2', 'inference_v1'
    model_version TEXT NOT NULL,        -- Version identifier
    job_type TEXT NOT NULL,             -- Job type this model handles

    -- Performance Metrics
    prediction_accuracy REAL,          -- Accuracy of performance predictions (0-1)
    confidence_score REAL,             -- Average confidence of predictions (0-1)
    mse_score REAL,                     -- Mean squared error of predictions
    mae_score REAL,                     -- Mean absolute error

    -- Usage Statistics
    total_predictions INTEGER DEFAULT 0,
    correct_predictions INTEGER DEFAULT 0,
    evaluation_date TIMESTAMPTZ DEFAULT NOW(),

    -- A/B Testing Results
    ab_test_group TEXT,                 -- 'control' or 'treatment'
    performance_improvement REAL,      -- % improvement over baseline

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Training data for model retraining
CREATE TABLE training_data (
    id SERIAL PRIMARY KEY,
    job_id TEXT NOT NULL,
    gpu_id TEXT NOT NULL,

    -- Input Features (at job scheduling time)
    features JSONB NOT NULL,           -- All input features as JSON

    -- Target Labels (after job completion)
    labels JSONB NOT NULL,             -- Performance outcomes as JSON

    -- Metadata
    job_type TEXT NOT NULL,
    data_quality_score REAL DEFAULT 1.0, -- Quality of this training sample (0-1)
    is_training_run BOOLEAN DEFAULT FALSE, -- Whether this was a dedicated training run
    model_version_used TEXT,           -- Which model made the prediction
    prediction_made JSONB,             -- What the model predicted

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Model deployment tracking
CREATE TABLE model_deployments (
    id SERIAL PRIMARY KEY,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    deployment_type TEXT NOT NULL,     -- 'full', 'ab_test', 'canary'
    deployment_percentage INTEGER DEFAULT 100, -- % of traffic using this model

    -- Deployment Status
    status TEXT DEFAULT 'active',      -- 'active', 'deprecated', 'rollback'
    deployed_at TIMESTAMPTZ DEFAULT NOW(),
    deprecated_at TIMESTAMPTZ,

    -- Performance Tracking
    total_predictions INTEGER DEFAULT 0,
    success_rate REAL,
    average_confidence REAL,

    -- Rollback Information
    previous_model_version TEXT,
    rollback_reason TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for performance queries
CREATE INDEX idx_job_performance_job_id ON job_performance (job_id);
CREATE INDEX idx_job_performance_gpu_id ON job_performance (gpu_id, start_time DESC);
CREATE INDEX idx_job_performance_job_type ON job_performance (job_type, start_time DESC);
CREATE INDEX idx_job_performance_start_time ON job_performance (start_time DESC);

CREATE INDEX idx_model_performance_name_version ON model_performance (model_name, model_version);
CREATE INDEX idx_model_performance_job_type ON model_performance (job_type, evaluation_date DESC);

CREATE INDEX idx_training_data_job_type ON training_data (job_type, created_at DESC);
CREATE INDEX idx_training_data_gpu_id ON training_data (gpu_id, created_at DESC);
CREATE INDEX idx_training_data_quality ON training_data (data_quality_score DESC) WHERE data_quality_score > 0.8;

CREATE INDEX idx_model_deployments_active ON model_deployments (model_name, status) WHERE status = 'active';
