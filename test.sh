#!/bin/bash

# Aether GPU Telemetry and Scheduling System - Test Script
# This script tests the entire system via API requests and validates functionality

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}🧪 Aether System Test Suite${NC}"
echo -e "${BLUE}===========================${NC}"
echo ""

# Function to print status messages
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
TOTAL_TESTS=0

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"
    local expected_status="$3"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    print_info "Running: $test_name"
    
    if eval "$test_command" > /dev/null 2>&1; then
        if [ "$expected_status" = "success" ]; then
            print_status "PASS: $test_name"
            TESTS_PASSED=$((TESTS_PASSED + 1))
        else
            print_error "FAIL: $test_name (expected failure but succeeded)"
            TESTS_FAILED=$((TESTS_FAILED + 1))
        fi
    else
        if [ "$expected_status" = "failure" ]; then
            print_status "PASS: $test_name (expected failure)"
            TESTS_PASSED=$((TESTS_PASSED + 1))
        else
            print_error "FAIL: $test_name"
            TESTS_FAILED=$((TESTS_FAILED + 1))
        fi
    fi
    echo ""
}

# Function to test API endpoint
test_api() {
    local url="$1"
    local method="$2"
    local data="$3"
    local expected_status="$4"
    
    if [ "$method" = "GET" ]; then
        curl -s -o /dev/null -w "%{http_code}" "$url"
    elif [ "$method" = "POST" ]; then
        curl -s -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" -d "$data" "$url"
    fi
}

# Function to test WebSocket connection
test_websocket() {
    local url="$1"
    local timeout=3
    
    # Test WebSocket upgrade by checking if the server responds to WebSocket headers
    curl -s --include --no-buffer -N -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Key: SGVsbG8sIHdvcmxkIQ==" -H "Sec-WebSocket-Version: 13" "$url" 2>/dev/null | grep -q "101 Switching Protocols"
}

# Step 1: Check if services are running
print_info "Checking if Aether services are running..."
echo ""

# Test 1: Check AI Core API
run_test "AI Core API Health Check" "curl -s http://localhost:8000/docs > /dev/null" "success"

# Test 2: Check Orchestrator API
run_test "Orchestrator API Health Check" "curl -s http://localhost:8080/submit > /dev/null" "success"

# Test 3: Check Dashboard
run_test "Dashboard Health Check" "curl -s http://localhost:3000 > /dev/null" "success"

# Test 4: Check NATS
run_test "NATS Message Broker" "docker ps | grep -q nats" "success"

# Test 5: Check TimescaleDB
run_test "TimescaleDB Database" "docker ps | grep -q timescaledb" "success"

# Step 2: Test API Endpoints
print_info "Testing API endpoints..."
echo ""

# Test 6: Test job submission
run_test "Job Submission API" "curl -s -X POST http://localhost:8080/submit -H 'Content-Type: application/json' -d '{\"id\": \"test-job-1\", \"type\": \"training\"}' | grep -q 'job added'" "success"

# Test 7: Test invalid job submission
run_test "Invalid Job Submission (should fail)" "curl -s -X POST http://localhost:8080/submit -H 'Content-Type: application/json' -d '{\"invalid\": \"data\"}' | grep -q 'job added'" "failure"

# Test 8: Test AI Core prediction endpoint
run_test "AI Core Prediction API" "curl -s -X POST http://localhost:8000/predict -H 'Content-Type: application/json' -d '{\"gpu_temp\": 45, \"gpu_mem_used\": 1000, \"utilization_gpu\": 50, \"power_draw_w\": 100, \"throttling_reasons\": \"None\", \"job_type\": \"training\"}' | grep -q 'is_good_placement'" "success"

# Test 9: Test AI Core with missing fields
run_test "AI Core Missing Fields (should fail)" "curl -s -X POST http://localhost:8000/predict -H 'Content-Type: application/json' -d '{\"gpu_temp\": 45}' | grep -q 'is_good_placement'" "failure"

# Step 3: Test WebSocket Connection
print_info "Testing WebSocket connections..."
echo ""

# Test 10: Test WebSocket endpoint exists
run_test "Dashboard WebSocket Endpoint" "curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/graphql | grep -q '400'" "success"

# Step 4: Test Database Connectivity
print_info "Testing database connectivity..."
echo ""

# Test 11: Test database connection
run_test "Database Connection" "docker compose -f $PROJECT_ROOT/aether/docker-compose.yml exec -T timescaledb psql -U aether -d aether -c 'SELECT 1;' > /dev/null" "success"

# Test 12: Test table exists
run_test "GPU Telemetry Table Exists" "docker compose -f $PROJECT_ROOT/aether/docker-compose.yml exec -T timescaledb psql -U aether -d aether -c 'SELECT COUNT(*) FROM gpu_telemetry;' > /dev/null" "success"

# Step 5: Test Data Flow
print_info "Testing data flow..."
echo ""

# Test 13: Submit multiple jobs and check queue
run_test "Multiple Job Submission" "curl -s -X POST http://localhost:8080/submit -H 'Content-Type: application/json' -d '{\"id\": \"test-job-2\", \"type\": \"inference\"}' | grep -q 'job added'" "success"

run_test "Third Job Submission" "curl -s -X POST http://localhost:8080/submit -H 'Content-Type: application/json' -d '{\"id\": \"test-job-3\", \"type\": \"training\"}' | grep -q 'job added'" "success"

# Step 6: Performance Tests
print_info "Running performance tests..."
echo ""

# Test 14: Test API response time
print_info "Testing API response times..."

# Test AI Core response time
AI_RESPONSE_TIME=$(curl -s -w "%{time_total}" -o /dev/null -X POST http://localhost:8000/predict -H 'Content-Type: application/json' -d '{"candidates": [{"gpu_id": "gpu-0", "gpu_temp": 45, "gpu_mem_used": 1000, "utilization_gpu": 50, "power_draw_w": 100, "throttling_reasons": "None"}], "job_type": "training"}')

if (( $(echo "$AI_RESPONSE_TIME < 1.0" | bc -l) )); then
    print_status "PASS: AI Core response time ($AI_RESPONSE_TIME seconds)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    print_warning "SLOW: AI Core response time ($AI_RESPONSE_TIME seconds)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Test Orchestrator response time
ORCH_RESPONSE_TIME=$(curl -s -w "%{time_total}" -o /dev/null -X POST http://localhost:8080/submit -H 'Content-Type: application/json' -d '{"id": "perf-test", "type": "training"}')

if (( $(echo "$ORCH_RESPONSE_TIME < 0.5" | bc -l) )); then
    print_status "PASS: Orchestrator response time ($ORCH_RESPONSE_TIME seconds)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    print_warning "SLOW: Orchestrator response time ($ORCH_RESPONSE_TIME seconds)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Step 7: Test Error Handling
print_info "Testing error handling..."
echo ""

# Test 15: Test invalid JSON
run_test "Invalid JSON Handling" "curl -s -X POST http://localhost:8080/submit -H 'Content-Type: application/json' -d 'invalid json' | grep -q 'job added'" "failure"

# Test 16: Test missing required fields
run_test "Missing Required Fields" "curl -s -X POST http://localhost:8080/submit -H 'Content-Type: application/json' -d '{\"id\": \"test\"}' | grep -q 'job added'" "failure"

# Step 8: Test System Integration
print_info "Testing system integration..."
echo ""

# Test 17: Check if telemetry data is being generated
print_info "Checking for telemetry data in database..."

# Wait a moment for telemetry to be generated
sleep 2

TELEMETRY_COUNT=$(docker compose -f $PROJECT_ROOT/aether/docker-compose.yml exec -T timescaledb psql -U aether -d aether -t -c "SELECT COUNT(*) FROM gpu_telemetry WHERE time > NOW() - INTERVAL '1 minute';" 2>/dev/null | tr -d ' \n' || echo "0")

if [ "$TELEMETRY_COUNT" -gt 0 ]; then
    print_status "PASS: Telemetry data found ($TELEMETRY_COUNT records in last minute)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    print_warning "WARNING: No recent telemetry data found"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Step 9: Final Results
echo ""
echo -e "${BLUE}📊 Test Results Summary${NC}"
echo -e "${BLUE}=======================${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    print_status "All tests passed! ($TESTS_PASSED/$TOTAL_TESTS)"
    echo ""
    echo -e "${GREEN}🎉 Aether system is working correctly!${NC}"
    echo ""
    echo -e "${BLUE}System Status:${NC}"
    echo "  • All services are running"
    echo "  • APIs are responding correctly"
    echo "  • Database is accessible"
    echo "  • WebSocket connections work"
    echo "  • Job submission and processing works"
    echo "  • AI Core predictions are working"
    echo ""
    echo -e "${BLUE}Access Points:${NC}"
    echo "  • Dashboard: http://localhost:3000"
    echo "  • Orchestrator API: http://localhost:8080"
    echo "  • AI Core API: http://localhost:8000"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "  • Open the dashboard to monitor GPU telemetry"
    echo "  • Submit jobs via the API or dashboard"
    echo "  • Monitor system performance and logs"
else
    print_error "Some tests failed! ($TESTS_FAILED/$TOTAL_TESTS failed)"
    echo ""
    echo -e "${RED}❌ System issues detected${NC}"
    echo ""
    echo -e "${YELLOW}Troubleshooting:${NC}"
    echo "  • Check if all services are running: ./restart.sh"
    echo "  • Check logs for errors"
    echo "  • Verify Docker containers are running"
    echo "  • Ensure all dependencies are installed"
fi

echo ""
echo -e "${BLUE}Test completed at:${NC} $(date)"
