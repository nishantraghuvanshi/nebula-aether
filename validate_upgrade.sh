#!/bin/bash

# Nebula Aether Phase 1 Upgrade Validation Script
# Tests the enhanced telemetry system and AI-integrated job scheduling

set -e  # Exit on any error

echo "🚀 Nebula Aether Phase 1 Upgrade Validation"
echo "============================================="

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0
TOTAL_TESTS=0

run_test() {
    local test_name=$1
    local test_command=$2

    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    print_status $BLUE "📋 Test $TOTAL_TESTS: $test_name"

    if eval "$test_command"; then
        print_status $GREEN "✅ PASSED: $test_name"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        print_status $RED "❌ FAILED: $test_name"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Test 1: Verify database schema has all required fields
test_database_schema() {
    print_status $YELLOW "Checking database schema..."

    # Check if TimescaleDB is running
    if ! docker ps | grep -q timescaledb; then
        print_status $RED "TimescaleDB container not running. Start with: docker compose up -d"
        return 1
    fi

    # Check if schema has all required fields
    local required_fields=("gpu_id" "utilization_gpu" "utilization_memory_controller"
                          "performance_state" "clock_gpu_mhz" "clock_mem_mhz"
                          "power_draw_w" "throttling_reasons")

    for field in "${required_fields[@]}"; do
        if docker exec nebula-aether-timescaledb-1 psql -U aether -d aether -c "\d gpu_telemetry" | grep -q "$field"; then
            print_status $GREEN "  ✓ Field '$field' exists"
        else
            print_status $RED "  ✗ Field '$field' missing"
            return 1
        fi
    done

    return 0
}

# Test 2: Check if NATS is accessible
test_nats_connectivity() {
    print_status $YELLOW "Testing NATS connectivity..."

    if ! docker ps | grep -q nats; then
        print_status $RED "NATS container not running. Start with: docker compose up -d"
        return 1
    fi

    # Test NATS connection (requires nats CLI tool)
    if command -v nats &> /dev/null; then
        if nats --server nats://0.tcp.in.ngrok.io:12133 server check; then
            return 0
        else
            print_status $RED "Cannot connect to NATS server"
            return 1
        fi
    else
        print_status $YELLOW "NATS CLI not available, skipping connectivity test"
        return 0
    fi
}

# Test 3: Verify orchestrator can start and load job definitions
test_orchestrator_startup() {
    print_status $YELLOW "Testing orchestrator startup..."

    cd apps/orchestrator

    # Check if go.mod exists
    if [[ ! -f "go.mod" ]]; then
        print_status $RED "go.mod not found in orchestrator directory"
        return 1
    fi

    # Try to build the orchestrator
    if go build -o orchestrator_test .; then
        print_status $GREEN "  ✓ Orchestrator builds successfully"
        rm -f orchestrator_test
    else
        print_status $RED "  ✗ Orchestrator build failed"
        return 1
    fi

    cd ../..
    return 0
}

# Test 4: Verify AI core can start and load models
test_ai_core_startup() {
    print_status $YELLOW "Testing AI core startup..."

    cd apps/ai-core

    # Check if Python dependencies are available
    if python3 -c "import fastapi, pandas, joblib" 2>/dev/null; then
        print_status $GREEN "  ✓ Required Python packages available"
    else
        print_status $RED "  ✗ Missing Python dependencies (fastapi, pandas, joblib)"
        cd ../..
        return 1
    fi

    # Check if we can import the main module
    if python3 -c "from main import app" 2>/dev/null; then
        print_status $GREEN "  ✓ AI core module loads successfully"
    else
        print_status $RED "  ✗ AI core module has import errors"
        cd ../..
        return 1
    fi

    cd ../..
    return 0
}

# Test 5: Verify job definitions are loadable
test_job_definitions() {
    print_status $YELLOW "Testing job definitions..."

    if [[ -f "demo-jobs/job-definitions.json" ]]; then
        # Validate JSON syntax
        if python3 -c "import json; json.load(open('demo-jobs/job-definitions.json'))" 2>/dev/null; then
            print_status $GREEN "  ✓ Job definitions JSON is valid"

            # Count job types
            local job_count=$(python3 -c "import json; data=json.load(open('demo-jobs/job-definitions.json')); print(len(data))")
            print_status $GREEN "  ✓ Found $job_count job definitions"

            return 0
        else
            print_status $RED "  ✗ Job definitions JSON is invalid"
            return 1
        fi
    else
        print_status $RED "  ✗ Job definitions file not found"
        return 1
    fi
}

# Test 6: Check if agent build works
test_agent_build() {
    print_status $YELLOW "Testing Rust agent build..."

    cd apps/agent

    # Check if Cargo.toml exists
    if [[ ! -f "Cargo.toml" ]]; then
        print_status $RED "Cargo.toml not found in agent directory"
        cd ../..
        return 1
    fi

    # Try to build in check mode (faster than full build)
    if cargo check 2>/dev/null; then
        print_status $GREEN "  ✓ Rust agent code compiles successfully"
    else
        print_status $RED "  ✗ Rust agent has compilation errors"
        cd ../..
        return 1
    fi

    cd ../..
    return 0
}

# Test 7: Validate demo job scripts
test_demo_jobs() {
    print_status $YELLOW "Testing demo job scripts..."

    local script_errors=0

    for script in demo-jobs/*.py; do
        if [[ -f "$script" ]]; then
            # Basic syntax check
            if python3 -m py_compile "$script" 2>/dev/null; then
                print_status $GREEN "  ✓ $(basename "$script") syntax OK"
            else
                print_status $RED "  ✗ $(basename "$script") has syntax errors"
                script_errors=$((script_errors + 1))
            fi
        fi
    done

    if [[ $script_errors -eq 0 ]]; then
        return 0
    else
        return 1
    fi
}

# Test 8: Check Docker services
test_docker_services() {
    print_status $YELLOW "Testing Docker infrastructure services..."

    local required_services=("timescaledb" "nats")
    local missing_services=0

    for service in "${required_services[@]}"; do
        if docker ps --format "table {{.Names}}" | grep -q "$service"; then
            print_status $GREEN "  ✓ $service container running"
        else
            print_status $RED "  ✗ $service container not running"
            missing_services=$((missing_services + 1))
        fi
    done

    if [[ $missing_services -eq 0 ]]; then
        return 0
    else
        print_status $YELLOW "  💡 Start services with: docker compose up -d"
        return 1
    fi
}

# Run all tests
echo ""
print_status $BLUE "Starting validation tests..."
echo ""

run_test "Docker Infrastructure Services" "test_docker_services"
run_test "Database Schema Validation" "test_database_schema"
run_test "NATS Connectivity" "test_nats_connectivity"
run_test "Job Definitions Format" "test_job_definitions"
run_test "Demo Job Scripts Syntax" "test_demo_jobs"
run_test "Orchestrator Build" "test_orchestrator_startup"
run_test "AI Core Dependencies" "test_ai_core_startup"
run_test "Rust Agent Compilation" "test_agent_build"

# Print summary
echo ""
print_status $BLUE "============================================="
print_status $BLUE "Validation Summary"
print_status $BLUE "============================================="

if [[ $TESTS_FAILED -eq 0 ]]; then
    print_status $GREEN "🎉 All $TOTAL_TESTS tests passed! System ready for Phase 1 upgrade."

    echo ""
    print_status $BLUE "Next Steps:"
    print_status $YELLOW "1. Restart database: docker compose down && docker compose up -d"
    print_status $YELLOW "2. Start orchestrator: cd apps/orchestrator && go run ."
    print_status $YELLOW "3. Start AI core: cd apps/ai-core && python main.py"
    print_status $YELLOW "4. Start agent: cd apps/agent && cargo run --release"
    print_status $YELLOW "5. Test job submission: ./submit_job.sh monte-carlo-simulation"

    exit 0
else
    print_status $RED "❌ $TESTS_FAILED out of $TOTAL_TESTS tests failed."
    print_status $RED "Please fix the issues above before proceeding with the upgrade."
    exit 1
fi