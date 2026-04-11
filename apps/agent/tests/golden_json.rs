//! Wire-format golden test for the NATS telemetry payload.
//!
//! The Go orchestrator at `apps/orchestrator/main.go` decodes telemetry
//! messages published on `aether.telemetry.*` by matching exact field names
//! against `GpuTelemetry`'s JSON encoding. Any accidental change to the
//! serialized bytes — field reorder, rename, type change, drop — would
//! silently break the orchestrator's decoder.
//!
//! This test pins the wire format by serializing a deterministic
//! `GpuTelemetry` fixture and asserting byte equality against a checked-in
//! expected string. Perf work that touches serialization (buffer reuse,
//! simd-json, field interning) must not change these bytes.
//!
//! If a legitimate schema change is needed, update BOTH this expected
//! constant AND `apps/orchestrator/main.go`'s decoder in the same change.

use agent::hotpath::{build_gpu_telemetry, GpuSampleInputs};

/// Deterministic fixture mirroring `benches/telemetry_hotpath.rs::fixtures`.
fn fixture_inputs() -> GpuSampleInputs {
    GpuSampleInputs {
        gpu_index: 0,
        gpu_name: "NVIDIA A100-SXM4-40GB".to_string(),
        utilization_gpu: 72,
        utilization_memory: 55,
        performance_state: "P0".to_string(),
        clock_gpu_mhz: 1410,
        clock_mem_mhz: 1215,
        memory_used_bytes: 24_000_000_000,
        memory_total_bytes: 42_949_672_960,
        temperature_c: 68,
        power_draw_w: 310,
        throttling_reasons: "GpuIdle".to_string(),
    }
}

const EXPECTED_WIRE_JSON: &str = concat!(
    r#"{"gpu_id":"runpod-host-abc123:gpu-0","#,
    r#""gpu_name":"NVIDIA A100-SXM4-40GB","#,
    r#""utilization_gpu":72,"#,
    r#""utilization_memory_controller":55,"#,
    r#""performance_state":"P0","#,
    r#""clock_gpu_mhz":1410,"#,
    r#""clock_mem_mhz":1215,"#,
    r#""memory_used_mb":22888,"#,
    r#""memory_total_mb":40960,"#,
    r#""temperature_c":68,"#,
    r#""power_draw_w":310,"#,
    r#""throttling_reasons":"GpuIdle""#,
    r#"}"#,
);

#[test]
fn telemetry_wire_format_is_stable() {
    let telemetry = build_gpu_telemetry("runpod-host-abc123", fixture_inputs());
    let bytes = serde_json::to_vec(&telemetry).expect("telemetry must serialize");
    let actual = std::str::from_utf8(&bytes).expect("telemetry JSON must be valid UTF-8");

    assert_eq!(
        actual, EXPECTED_WIRE_JSON,
        "\n\nGpuTelemetry wire format changed. If this is intentional, update \
         BOTH this test AND apps/orchestrator/main.go's NATS telemetry decoder \
         in the same change.\n"
    );
}

#[test]
fn telemetry_memory_mb_arithmetic() {
    // Sanity-check the bytes -> MB integer division used inside
    // build_gpu_telemetry. If anyone "fixes" this to use rounding division
    // or a different unit, the wire format changes and the above golden
    // test will also fail — but this test pinpoints the cause.
    let telemetry = build_gpu_telemetry("runpod-host-abc123", fixture_inputs());
    assert_eq!(telemetry.memory_used_mb, 22_888);
    assert_eq!(telemetry.memory_total_mb, 40_960);
    assert_eq!(telemetry.gpu_id, "runpod-host-abc123:gpu-0");
}
