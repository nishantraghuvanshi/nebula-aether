#!/bin/bash

# Aether Job Submission Script
# Usage: ./submit_job.sh [job_id] [job_type]
# Example: ./submit_job.sh training-job-001 training

set -e

# Default values
DEFAULT_JOB_ID="job-$(date +%s)"
DEFAULT_JOB_TYPE="training"
ORCHESTRATOR_URL="http://localhost:8080"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [job_id] [job_type]"
    echo ""
    echo "Arguments:"
    echo "  job_id    Job identifier (default: job-<timestamp>)"
    echo "  job_type  Job type: 'training' or 'inference' (default: training)"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Submit with auto-generated ID"
    echo "  $0 my-training-job                    # Submit training job with custom ID"
    echo "  $0 my-inference-job inference         # Submit inference job with custom ID"
    echo "  $0 batch-job-001 training             # Submit training job with specific ID"
    echo ""
    echo "Environment Variables:"
    echo "  ORCHESTRATOR_URL  Override orchestrator URL (default: http://localhost:8080)"
}

# Function to check if orchestrator is running
check_orchestrator() {
    print_status "Checking orchestrator availability..."
    
    # Check if port 8080 is listening
    if command -v nc >/dev/null 2>&1; then
        if nc -z localhost 8080 2>/dev/null; then
            print_success "Orchestrator is running at $ORCHESTRATOR_URL"
            return 0
        fi
    elif command -v telnet >/dev/null 2>&1; then
        if timeout 3 telnet localhost 8080 </dev/null 2>/dev/null | grep -q "Connected"; then
            print_success "Orchestrator is running at $ORCHESTRATOR_URL"
            return 0
        fi
    else
        # Fallback: try a simple HTTP request
        if curl -s --connect-timeout 3 "$ORCHESTRATOR_URL" >/dev/null 2>&1; then
            print_success "Orchestrator is running at $ORCHESTRATOR_URL"
            return 0
        fi
    fi
    
    print_error "Orchestrator is not responding at $ORCHESTRATOR_URL"
    print_warning "Make sure the orchestrator is running:"
    print_warning "  cd aether/apps/orchestrator && go run main.go"
    return 1
}

# Function to submit job
submit_job() {
    local job_id="$1"
    local job_type="$2"
    
    print_status "Submitting job..."
    print_status "  Job ID: $job_id"
    print_status "  Job Type: $job_type"
    print_status "  Target: $ORCHESTRATOR_URL/submit"
    
    # Create JSON payload
    local json_payload=$(cat <<EOF
{
    "id": "$job_id",
    "type": "$job_type"
}
EOF
)
    
    # Submit the job
    local response=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "$json_payload" \
        "$ORCHESTRATOR_URL/submit")
    
    # Extract HTTP status code (last line)
    local http_code=$(echo "$response" | tail -n1)
    local response_body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" -eq 201 ]; then
        print_success "Job submitted successfully!"
        print_success "Response: $response_body"
        return 0
    else
        print_error "Failed to submit job (HTTP $http_code)"
        print_error "Response: $response_body"
        return 1
    fi
}

# Function to submit multiple jobs
submit_batch() {
    local job_type="$1"
    local count="${2:-5}"
    
    print_status "Submitting batch of $count $job_type jobs..."
    
    local success_count=0
    local fail_count=0
    
    for i in $(seq 1 "$count"); do
        local job_id="batch-${job_type}-$(printf "%03d" $i)-$(date +%s)"
        
        if submit_job "$job_id" "$job_type"; then
            ((success_count++))
        else
            ((fail_count++))
        fi
        
        # Small delay between submissions
        sleep 0.5
    done
    
    print_status "Batch submission complete:"
    print_success "  Successful: $success_count"
    if [ $fail_count -gt 0 ]; then
        print_error "  Failed: $fail_count"
    fi
}

# Function to show job queue status (if available)
show_queue_status() {
    print_status "Checking job queue status..."
    
    # This would require a new endpoint in the orchestrator
    # For now, just show a placeholder
    print_warning "Queue status endpoint not yet implemented"
}

# Main script logic
main() {
    # Parse command line arguments
    case "${1:-}" in
        -h|--help)
            show_usage
            exit 0
            ;;
        -b|--batch)
            if [ -z "${2:-}" ]; then
                print_error "Batch mode requires job type"
                show_usage
                exit 1
            fi
            local job_type="$2"
            local count="${3:-5}"
            
            if [ "$job_type" != "training" ] && [ "$job_type" != "inference" ]; then
                print_error "Invalid job type: $job_type"
                print_error "Must be 'training' or 'inference'"
                exit 1
            fi
            
            if ! check_orchestrator; then
                exit 1
            fi
            
            submit_batch "$job_type" "$count"
            ;;
        -s|--status)
            if ! check_orchestrator; then
                exit 1
            fi
            show_queue_status
            ;;
        *)
            # Regular job submission
            local job_id="${1:-$DEFAULT_JOB_ID}"
            local job_type="${2:-$DEFAULT_JOB_TYPE}"
            
            # Validate job type
            if [ "$job_type" != "training" ] && [ "$job_type" != "inference" ]; then
                print_error "Invalid job type: $job_type"
                print_error "Must be 'training' or 'inference'"
                exit 1
            fi
            
            # Check orchestrator availability
            if ! check_orchestrator; then
                exit 1
            fi
            
            # Submit the job
            submit_job "$job_id" "$job_type"
            ;;
    esac
}

# Run main function with all arguments
main "$@"
