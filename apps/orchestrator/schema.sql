CREATE TABLE gpu_telemetry (
    time TIMESTAMPTZ NOT NULL,
    gpu_name TEXT,
    temperature_c INTEGER,
    memory_used_mb BIGINT,
    memory_total_mb BIGINT
);

SELECT create_hypertable('gpu_telemetry', 'time');
