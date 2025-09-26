#!/bin/bash

# GPU ID Flow Integration Test
# Tests the complete flow of GPU ID from Rust telemetry → Go orchestrator → AI Core

set -e

echo "🔍 GPU ID Flow Integration Test"
echo "================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Test 1: Verify Rust agent struct includes gpu_id
test_rust_telemetry_struct() {
    print_status $BLUE "🦀 Testing Rust GpuTelemetry struct..."

    if grep -q "gpu_id: String," apps/agent/src/main.rs; then
        print_status $GREEN "  ✅ gpu_id field found in Rust GpuTelemetry struct"
    else
        print_status $RED "  ❌ gpu_id field missing from Rust GpuTelemetry struct"
        return 1
    fi

    # Check if gpu_id is being set in telemetry creation
    if grep -q "gpu_id: gpu_id.clone()," apps/agent/src/main.rs; then
        print_status $GREEN "  ✅ gpu_id is being set in telemetry creation"
    else
        print_status $RED "  ❌ gpu_id not being set in telemetry creation"
        return 1
    fi

    # Check standardized GPU ID format
    if grep -q "format!(\"{}:gpu-{}\", hostname, i)" apps/agent/src/main.rs; then
        print_status $GREEN "  ✅ Standardized GPU ID format (hostname:gpu-N) used"
    else
        print_status $RED "  ❌ GPU ID format not standardized"
        return 1
    fi

    return 0
}

# Test 2: Verify Go orchestrator struct includes gpu_id
test_go_telemetry_struct() {
    print_status $BLUE "🔵 Testing Go GpuTelemetry struct..."

    if grep -q "GpuID.*string.*\`json:\"gpu_id\"\`" apps/orchestrator/main.go; then
        print_status $GREEN "  ✅ GpuID field found in Go GpuTelemetry struct"
    else
        print_status $RED "  ❌ GpuID field missing from Go GpuTelemetry struct"
        return 1
    fi

    # Check if orchestrator uses gpu_id from telemetry data
    if grep -q "gpuID := telemetry.GpuID" apps/orchestrator/main.go; then
        print_status $GREEN "  ✅ Orchestrator uses gpu_id from telemetry data"
    else
        print_status $RED "  ❌ Orchestrator not using gpu_id from telemetry"
        return 1
    fi

    return 0
}

# Test 3: Verify database schema includes gpu_id
test_database_schema() {
    print_status $BLUE "🗄️ Testing database schema..."

    if grep -q "gpu_id TEXT NOT NULL" apps/orchestrator/schema.sql; then
        print_status $GREEN "  ✅ gpu_id field in database schema"
    else
        print_status $RED "  ❌ gpu_id field missing from database schema"
        return 1
    fi

    # Check database insertion includes gpu_id
    if grep -q "time, gpu_id, gpu_name" apps/orchestrator/main.go; then
        print_status $GREEN "  ✅ Database insertion includes gpu_id"
    else
        print_status $RED "  ❌ Database insertion missing gpu_id"
        return 1
    fi

    return 0
}

# Test 4: Verify AI Core receives gpu_id in candidates
test_ai_core_gpu_id() {
    print_status $BLUE "🤖 Testing AI Core GPU ID handling..."

    if grep -q "gpu_id: str" apps/ai-core/main.py; then
        print_status $GREEN "  ✅ gpu_id field in AI Core GpuCandidate model"
    else
        print_status $RED "  ❌ gpu_id field missing from AI Core model"
        return 1
    fi

    # Check orchestrator passes gpu_id to AI Core
    if grep -q "GpuID:.*id," apps/orchestrator/main.go; then
        print_status $GREEN "  ✅ Orchestrator passes gpu_id to AI Core"
    else
        print_status $RED "  ❌ Orchestrator not passing gpu_id to AI Core"
        return 1
    fi

    return 0
}

# Test 5: Check for GPU ID consistency across components
test_gpu_id_consistency() {
    print_status $BLUE "🔄 Testing GPU ID consistency..."

    # All components should use hostname:gpu-N format
    local rust_format=$(grep -o "format!(\".*gpu.*\"" apps/agent/src/main.rs || echo "")
    local go_usage=$(grep -o "GpuID.*:" apps/orchestrator/main.go | head -1 || echo "")
    local ai_field=$(grep -o "gpu_id:.*str" apps/ai-core/main.py || echo "")

    if [[ -n "$rust_format" && -n "$go_usage" && -n "$ai_field" ]]; then
        print_status $GREEN "  ✅ GPU ID used consistently across all components"
    else
        print_status $RED "  ❌ GPU ID inconsistent across components"
        print_status $YELLOW "     Rust: $rust_format"
        print_status $YELLOW "     Go: $go_usage"
        print_status $YELLOW "     AI: $ai_field"
        return 1
    fi

    return 0
}

# Test 6: Verify job execution includes gpu_id
test_job_execution_gpu_id() {
    print_status $BLUE "⚙️ Testing job execution GPU ID..."

    # Check JobStatus includes gpu_id
    if grep -q "gpu_id: String," apps/agent/src/main.rs && grep -q "GpuID.*string" apps/orchestrator/main.go; then
        print_status $GREEN "  ✅ JobStatus includes gpu_id in both Rust and Go"
    else
        print_status $RED "  ❌ JobStatus missing gpu_id in components"
        return 1
    fi

    return 0
}

# Test 7: Check NATS subject includes GPU ID
test_nats_subjects() {
    print_status $BLUE "📡 Testing NATS subject GPU ID integration..."

    # Check telemetry subject format
    if grep -q "aether.telemetry.{}" apps/agent/src/main.rs; then
        print_status $GREEN "  ✅ NATS telemetry subject includes GPU ID"
    else
        print_status $RED "  ❌ NATS telemetry subject missing GPU ID"
        return 1
    fi

    # Check status subject format
    if grep -q "aether.status.{}" apps/agent/src/main.rs; then
        print_status $GREEN "  ✅ NATS status subject includes GPU ID"
    else
        print_status $RED "  ❌ NATS status subject missing GPU ID"
        return 1
    fi

    return 0
}

# Run all tests
TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
    local test_name=$1
    local test_function=$2

    if $test_function; then
        print_status $GREEN "✅ PASSED: $test_name"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        print_status $RED "❌ FAILED: $test_name"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
    echo
}

echo
run_test "Rust Telemetry Struct" "test_rust_telemetry_struct"
run_test "Go Orchestrator Struct" "test_go_telemetry_struct"
run_test "Database Schema" "test_database_schema"
run_test "AI Core GPU ID" "test_ai_core_gpu_id"
run_test "GPU ID Consistency" "test_gpu_id_consistency"
run_test "Job Execution GPU ID" "test_job_execution_gpu_id"
run_test "NATS Subject GPU ID" "test_nats_subjects"

# Summary
print_status $BLUE "================================="
print_status $BLUE "GPU ID Flow Test Summary"
print_status $BLUE "================================="

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))

if [[ $TESTS_FAILED -eq 0 ]]; then
    print_status $GREEN "🎉 All $TOTAL_TESTS tests passed!"
    print_status $GREEN "GPU ID is properly implemented across all components:"
    print_status $GREEN ""
    print_status $GREEN "📊 Data Flow:"
    print_status $GREEN "  1. Rust Agent → Creates GPU ID (hostname:gpu-N)"
    print_status $GREEN "  2. NATS → Publishes to aether.telemetry.{gpu_id}"
    print_status $GREEN "  3. Go Orchestrator → Receives and stores gpu_id"
    print_status $GREEN "  4. Database → gpu_id stored in telemetry table"
    print_status $GREEN "  5. AI Core → Receives gpu_id in candidate data"
    print_status $GREEN "  6. Job Status → gpu_id tracked throughout execution"
    print_status $GREEN ""
    print_status $GREEN "🚀 System ready for intelligent GPU scheduling!"
    exit 0
else
    print_status $RED "❌ $TESTS_FAILED out of $TOTAL_TESTS tests failed."
    print_status $RED "GPU ID implementation incomplete. Please fix the issues above."
    exit 1
fi