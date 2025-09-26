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
