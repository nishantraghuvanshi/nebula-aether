#!/bin/bash

# 🧹 Aether Codebase Cleanup Script
# This script removes temporary files, build artifacts, logs, and other generated content
# while preserving essential project files and source code.

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
DRY_RUN=false
VERBOSE=false
FORCE=false

# Statistics
TOTAL_SIZE_CLEANED=0
FILES_CLEANED=0
DIRECTORIES_CLEANED=0

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to get file size in human readable format
get_size() {
    local size=$(du -sh "$1" 2>/dev/null | cut -f1)
    echo "$size"
}

# Function to calculate total size cleaned
add_to_total() {
    local size_bytes=$(du -sb "$1" 2>/dev/null | cut -f1)
    TOTAL_SIZE_CLEANED=$((TOTAL_SIZE_CLEANED + size_bytes))
}

# Function to clean a file or directory
clean_item() {
    local item="$1"
    local description="$2"
    
    if [[ -e "$item" ]]; then
        local size=$(get_size "$item")
        
        if [[ "$DRY_RUN" == "true" ]]; then
            print_info "Would remove: $item ($size) - $description"
        else
            if [[ "$VERBOSE" == "true" ]]; then
                print_info "Removing: $item ($size) - $description"
            fi
            
            if [[ -d "$item" ]]; then
                rm -rf "$item"
                DIRECTORIES_CLEANED=$((DIRECTORIES_CLEANED + 1))
            else
                rm -f "$item"
                FILES_CLEANED=$((FILES_CLEANED + 1))
            fi
            
            add_to_total "$item"
            print_success "Removed: $item ($size)"
        fi
    fi
}

# Function to clean Rust build artifacts
clean_rust_artifacts() {
    print_info "Cleaning Rust build artifacts..."
    
    # Rust target directories
    find "$PROJECT_ROOT" -name "target" -type d -exec clean_item {} "Rust build artifacts" \;
    
    # Cargo lock files (optional - uncomment if needed)
    # find "$PROJECT_ROOT" -name "Cargo.lock" -type f -exec clean_item {} "Cargo lock file" \;
    
    # Rust incremental compilation cache
    find "$PROJECT_ROOT" -path "*/target/debug/incremental/*" -type d -exec clean_item {} "Rust incremental cache" \;
    find "$PROJECT_ROOT" -path "*/target/release/incremental/*" -type d -exec clean_item {} "Rust incremental cache" \;
}

# Function to clean Go build artifacts
clean_go_artifacts() {
    print_info "Cleaning Go build artifacts..."
    
    # Go binary files
    find "$PROJECT_ROOT" -name "orchestrator" -type f -exec clean_item {} "Go binary" \;
    find "$PROJECT_ROOT" -name "orchestrator-gang" -type f -exec clean_item {} "Go binary" \;
    
    # Go build cache
    if [[ -n "$GOCACHE" ]]; then
        clean_item "$GOCACHE" "Go build cache"
    fi
    
    # Go module cache (optional - uncomment if needed)
    # if [[ -n "$GOMODCACHE" ]]; then
    #     clean_item "$GOMODCACHE" "Go module cache"
    # fi
}

# Function to clean Python artifacts
clean_python_artifacts() {
    print_info "Cleaning Python artifacts..."
    
    # Python cache directories
    find "$PROJECT_ROOT" -name "__pycache__" -type d -exec clean_item {} "Python cache" \;
    find "$PROJECT_ROOT" -name "*.pyc" -type f -exec clean_item {} "Python bytecode" \;
    find "$PROJECT_ROOT" -name "*.pyo" -type f -exec clean_item {} "Python bytecode" \;
    
    # Python virtual environments
    find "$PROJECT_ROOT" -name "venv" -type d -exec clean_item {} "Python virtual environment" \;
    find "$PROJECT_ROOT" -name ".venv" -type d -exec clean_item {} "Python virtual environment" \;
    find "$PROJECT_ROOT" -name "env" -type d -exec clean_item {} "Python virtual environment" \;
    
    # Python distribution directories
    find "$PROJECT_ROOT" -name "*.egg-info" -type d -exec clean_item {} "Python package info" \;
    find "$PROJECT_ROOT" -name "dist" -type d -exec clean_item {} "Python distribution" \;
    find "$PROJECT_ROOT" -name "build" -type d -exec clean_item {} "Python build" \;
    
    # Python model files (optional - uncomment if needed)
    # find "$PROJECT_ROOT" -name "*.pkl" -type f -exec clean_item {} "Python pickle file" \;
}

# Function to clean Node.js artifacts
clean_nodejs_artifacts() {
    print_info "Cleaning Node.js artifacts..."
    
    # Node modules directories
    find "$PROJECT_ROOT" -name "node_modules" -type d -exec clean_item {} "Node.js dependencies" \;
    
    # Next.js build artifacts
    find "$PROJECT_ROOT" -name ".next" -type d -exec clean_item {} "Next.js build cache" \;
    find "$PROJECT_ROOT" -name "out" -type d -exec clean_item {} "Next.js output" \;
    
    # NPM/Yarn cache
    find "$PROJECT_ROOT" -name ".npm" -type d -exec clean_item {} "NPM cache" \;
    find "$PROJECT_ROOT" -name ".yarn" -type d -exec clean_item {} "Yarn cache" \;
    
    # Package lock files (optional - uncomment if needed)
    # find "$PROJECT_ROOT" -name "package-lock.json" -type f -exec clean_item {} "NPM lock file" \;
    # find "$PROJECT_ROOT" -name "yarn.lock" -type f -exec clean_item {} "Yarn lock file" \;
}

# Function to clean log files
clean_log_files() {
    print_info "Cleaning log files..."
    
    # Common log file patterns
    find "$PROJECT_ROOT" -name "*.log" -type f -exec clean_item {} "Log file" \;
    find "$PROJECT_ROOT" -name "*.log.*" -type f -exec clean_item {} "Rotated log file" \;
    
    # Application-specific log files
    find "$PROJECT_ROOT" -name "agent*.log" -type f -exec clean_item {} "Agent log file" \;
    find "$PROJECT_ROOT" -name "orchestrator*.log" -type f -exec clean_item {} "Orchestrator log file" \;
    find "$PROJECT_ROOT" -name "ai-core*.log" -type f -exec clean_item {} "AI Core log file" \;
    find "$PROJECT_ROOT" -name "dashboard*.log" -type f -exec clean_item {} "Dashboard log file" \;
    
    # Log backup directories
    find "$PROJECT_ROOT" -name "logs_backup_*" -type d -exec clean_item {} "Log backup directory" \;
}

# Function to clean temporary files
clean_temp_files() {
    print_info "Cleaning temporary files..."
    
    # Common temporary file patterns
    find "$PROJECT_ROOT" -name "*.tmp" -type f -exec clean_item {} "Temporary file" \;
    find "$PROJECT_ROOT" -name "*.temp" -type f -exec clean_item {} "Temporary file" \;
    find "$PROJECT_ROOT" -name "*.swp" -type f -exec clean_item {} "Vim swap file" \;
    find "$PROJECT_ROOT" -name "*.swo" -type f -exec clean_item {} "Vim swap file" \;
    find "$PROJECT_ROOT" -name "*~" -type f -exec clean_item {} "Backup file" \;
    find "$PROJECT_ROOT" -name ".#*" -type f -exec clean_item {} "Emacs lock file" \;
    
    # Process ID files
    find "$PROJECT_ROOT" -name "*.pid" -type f -exec clean_item {} "Process ID file" \;
    find "$PROJECT_ROOT" -name "aether.pids" -type f -exec clean_item {} "Process ID file" \;
    
    # OS-specific temporary files
    find "$PROJECT_ROOT" -name ".DS_Store" -type f -exec clean_item {} "macOS metadata" \;
    find "$PROJECT_ROOT" -name "Thumbs.db" -type f -exec clean_item {} "Windows thumbnail cache" \;
    find "$PROJECT_ROOT" -name "desktop.ini" -type f -exec clean_item {} "Windows desktop file" \;
}

# Function to clean backup files
clean_backup_files() {
    print_info "Cleaning backup files..."
    
    # Common backup file patterns
    find "$PROJECT_ROOT" -name "*.bak" -type f -exec clean_item {} "Backup file" \;
    find "$PROJECT_ROOT" -name "*.backup" -type f -exec clean_item {} "Backup file" \;
    find "$PROJECT_ROOT" -name "*.orig" -type f -exec clean_item {} "Original file backup" \;
    find "$PROJECT_ROOT" -name "*_backup.*" -type f -exec clean_item {} "Backup file" \;
    find "$PROJECT_ROOT" -name "*_old.*" -type f -exec clean_item {} "Old file" \;
    
    # Project-specific backup files
    find "$PROJECT_ROOT" -name "main.go.backup*" -type f -exec clean_item {} "Go backup file" \;
    find "$PROJECT_ROOT" -name "main_backup.md" -type f -exec clean_item {} "Markdown backup file" \;
}

# Function to clean test artifacts
clean_test_artifacts() {
    print_info "Cleaning test artifacts..."
    
    # Test output files
    find "$PROJECT_ROOT" -name "test_*.log" -type f -exec clean_item {} "Test log file" \;
    find "$PROJECT_ROOT" -name "*_test.log" -type f -exec clean_item {} "Test log file" \;
    find "$PROJECT_ROOT" -name "test-results.xml" -type f -exec clean_item {} "Test results" \;
    find "$PROJECT_ROOT" -name "coverage.xml" -type f -exec clean_item {} "Coverage report" \;
    
    # Test data files
    find "$PROJECT_ROOT" -name "test_data.csv" -type f -exec clean_item {} "Test data file" \;
    find "$PROJECT_ROOT" -name "training_data.csv" -type f -exec clean_item {} "Training data file" \;
}

# Function to clean Docker artifacts
clean_docker_artifacts() {
    print_info "Cleaning Docker artifacts..."
    
    # Docker volumes and containers (optional - uncomment if needed)
    # docker system prune -f 2>/dev/null || true
    
    # Docker build cache
    find "$PROJECT_ROOT" -name ".dockerignore" -type f -exec clean_item {} "Docker ignore file" \;
}

# Function to clean IDE/Editor artifacts
clean_ide_artifacts() {
    print_info "Cleaning IDE/Editor artifacts..."
    
    # VS Code
    find "$PROJECT_ROOT" -name ".vscode" -type d -exec clean_item {} "VS Code settings" \;
    
    # IntelliJ/WebStorm
    find "$PROJECT_ROOT" -name ".idea" -type d -exec clean_item {} "IntelliJ settings" \;
    
    # Vim
    find "$PROJECT_ROOT" -name ".vimrc" -type f -exec clean_item {} "Vim configuration" \;
    
    # Emacs
    find "$PROJECT_ROOT" -name ".emacs" -type f -exec clean_item {} "Emacs configuration" \;
    find "$PROJECT_ROOT" -name ".emacs.d" -type d -exec clean_item {} "Emacs directory" \;
}

# Function to clean system artifacts
clean_system_artifacts() {
    print_info "Cleaning system artifacts..."
    
    # Core dumps
    find "$PROJECT_ROOT" -name "core" -type f -exec clean_item {} "Core dump file" \;
    find "$PROJECT_ROOT" -name "core.*" -type f -exec clean_item {} "Core dump file" \;
    
    # System temporary files
    find "$PROJECT_ROOT" -name ".fuse_hidden*" -type f -exec clean_item {} "FUSE temporary file" \;
    find "$PROJECT_ROOT" -name ".nfs*" -type f -exec clean_item {} "NFS temporary file" \;
}

# Function to show help
show_help() {
    cat << EOF
🧹 Aether Codebase Cleanup Script

USAGE:
    $0 [OPTIONS]

OPTIONS:
    -h, --help          Show this help message
    -d, --dry-run       Show what would be cleaned without actually cleaning
    -v, --verbose       Show detailed output
    -f, --force         Skip confirmation prompts
    --rust-only         Clean only Rust artifacts
    --go-only           Clean only Go artifacts
    --python-only       Clean only Python artifacts
    --nodejs-only       Clean only Node.js artifacts
    --logs-only         Clean only log files
    --temp-only         Clean only temporary files
    --backup-only       Clean only backup files
    --test-only         Clean only test artifacts

EXAMPLES:
    $0                  # Clean all artifacts
    $0 --dry-run        # Show what would be cleaned
    $0 --verbose        # Show detailed cleaning process
    $0 --rust-only      # Clean only Rust build artifacts
    $0 --logs-only      # Clean only log files

DESCRIPTION:
    This script removes temporary files, build artifacts, logs, and other
    generated content from the Aether codebase while preserving essential
    project files and source code.

    The script will clean:
    - Rust build artifacts (target/, incremental cache)
    - Go build artifacts (binaries, build cache)
    - Python artifacts (__pycache__, .pyc files, virtual envs)
    - Node.js artifacts (node_modules/, .next/, build cache)
    - Log files (*.log, application logs)
    - Temporary files (*.tmp, *.swp, *.pid)
    - Backup files (*.bak, *.backup, *.orig)
    - Test artifacts (test logs, coverage reports)
    - IDE/Editor artifacts (.vscode/, .idea/)
    - System artifacts (core dumps, system temp files)

EOF
}

# Function to confirm cleanup
confirm_cleanup() {
    if [[ "$FORCE" == "true" ]]; then
        return 0
    fi
    
    echo -e "${YELLOW}⚠️  This will remove temporary files, build artifacts, and logs.${NC}"
    echo -e "${YELLOW}   Source code and essential project files will be preserved.${NC}"
    echo ""
    read -p "Are you sure you want to continue? (y/N): " -n 1 -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Cleanup cancelled."
        exit 0
    fi
}

# Function to format bytes to human readable
format_bytes() {
    local bytes=$1
    local units=("B" "KB" "MB" "GB" "TB")
    local unit=0
    
    while [[ $bytes -ge 1024 && $unit -lt 4 ]]; do
        bytes=$((bytes / 1024))
        unit=$((unit + 1))
    done
    
    echo "${bytes}${units[$unit]}"
}

# Function to show cleanup summary
show_summary() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo -e "${GREEN}🧹 CLEANUP SUMMARY${NC}"
    echo "═══════════════════════════════════════════════════════════════"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        print_info "DRY RUN - No files were actually removed"
    else
        print_success "Files cleaned: $FILES_CLEANED"
        print_success "Directories cleaned: $DIRECTORIES_CLEANED"
        print_success "Total space freed: $(format_bytes $TOTAL_SIZE_CLEANED)"
    fi
    
    echo ""
    print_info "Cleanup completed successfully! 🎉"
}

# Parse command line arguments
CLEAN_RUST=true
CLEAN_GO=true
CLEAN_PYTHON=true
CLEAN_NODEJS=true
CLEAN_LOGS=true
CLEAN_TEMP=true
CLEAN_BACKUP=true
CLEAN_TEST=true
CLEAN_DOCKER=true
CLEAN_IDE=true
CLEAN_SYSTEM=true

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        --rust-only)
            CLEAN_RUST=true
            CLEAN_GO=false
            CLEAN_PYTHON=false
            CLEAN_NODEJS=false
            CLEAN_LOGS=false
            CLEAN_TEMP=false
            CLEAN_BACKUP=false
            CLEAN_TEST=false
            CLEAN_DOCKER=false
            CLEAN_IDE=false
            CLEAN_SYSTEM=false
            shift
            ;;
        --go-only)
            CLEAN_RUST=false
            CLEAN_GO=true
            CLEAN_PYTHON=false
            CLEAN_NODEJS=false
            CLEAN_LOGS=false
            CLEAN_TEMP=false
            CLEAN_BACKUP=false
            CLEAN_TEST=false
            CLEAN_DOCKER=false
            CLEAN_IDE=false
            CLEAN_SYSTEM=false
            shift
            ;;
        --python-only)
            CLEAN_RUST=false
            CLEAN_GO=false
            CLEAN_PYTHON=true
            CLEAN_NODEJS=false
            CLEAN_LOGS=false
            CLEAN_TEMP=false
            CLEAN_BACKUP=false
            CLEAN_TEST=false
            CLEAN_DOCKER=false
            CLEAN_IDE=false
            CLEAN_SYSTEM=false
            shift
            ;;
        --nodejs-only)
            CLEAN_RUST=false
            CLEAN_GO=false
            CLEAN_PYTHON=false
            CLEAN_NODEJS=true
            CLEAN_LOGS=false
            CLEAN_TEMP=false
            CLEAN_BACKUP=false
            CLEAN_TEST=false
            CLEAN_DOCKER=false
            CLEAN_IDE=false
            CLEAN_SYSTEM=false
            shift
            ;;
        --logs-only)
            CLEAN_RUST=false
            CLEAN_GO=false
            CLEAN_PYTHON=false
            CLEAN_NODEJS=false
            CLEAN_LOGS=true
            CLEAN_TEMP=false
            CLEAN_BACKUP=false
            CLEAN_TEST=false
            CLEAN_DOCKER=false
            CLEAN_IDE=false
            CLEAN_SYSTEM=false
            shift
            ;;
        --temp-only)
            CLEAN_RUST=false
            CLEAN_GO=false
            CLEAN_PYTHON=false
            CLEAN_NODEJS=false
            CLEAN_LOGS=false
            CLEAN_TEMP=true
            CLEAN_BACKUP=false
            CLEAN_TEST=false
            CLEAN_DOCKER=false
            CLEAN_IDE=false
            CLEAN_SYSTEM=false
            shift
            ;;
        --backup-only)
            CLEAN_RUST=false
            CLEAN_GO=false
            CLEAN_PYTHON=false
            CLEAN_NODEJS=false
            CLEAN_LOGS=false
            CLEAN_TEMP=false
            CLEAN_BACKUP=true
            CLEAN_TEST=false
            CLEAN_DOCKER=false
            CLEAN_IDE=false
            CLEAN_SYSTEM=false
            shift
            ;;
        --test-only)
            CLEAN_RUST=false
            CLEAN_GO=false
            CLEAN_PYTHON=false
            CLEAN_NODEJS=false
            CLEAN_LOGS=false
            CLEAN_TEMP=false
            CLEAN_BACKUP=false
            CLEAN_TEST=true
            CLEAN_DOCKER=false
            CLEAN_IDE=false
            CLEAN_SYSTEM=false
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Main execution
main() {
    echo "🧹 Aether Codebase Cleanup Script"
    echo "═══════════════════════════════════════════════════════════════"
    
    # Change to project root
    cd "$PROJECT_ROOT"
    
    # Confirm cleanup unless dry run or force
    if [[ "$DRY_RUN" == "false" && "$FORCE" == "false" ]]; then
        confirm_cleanup
    fi
    
    print_info "Starting cleanup in: $PROJECT_ROOT"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        print_warning "DRY RUN MODE - No files will be actually removed"
    fi
    
    echo ""
    
    # Execute cleanup based on selected options
    if [[ "$CLEAN_RUST" == "true" ]]; then
        clean_rust_artifacts
    fi
    
    if [[ "$CLEAN_GO" == "true" ]]; then
        clean_go_artifacts
    fi
    
    if [[ "$CLEAN_PYTHON" == "true" ]]; then
        clean_python_artifacts
    fi
    
    if [[ "$CLEAN_NODEJS" == "true" ]]; then
        clean_nodejs_artifacts
    fi
    
    if [[ "$CLEAN_LOGS" == "true" ]]; then
        clean_log_files
    fi
    
    if [[ "$CLEAN_TEMP" == "true" ]]; then
        clean_temp_files
    fi
    
    if [[ "$CLEAN_BACKUP" == "true" ]]; then
        clean_backup_files
    fi
    
    if [[ "$CLEAN_TEST" == "true" ]]; then
        clean_test_artifacts
    fi
    
    if [[ "$CLEAN_DOCKER" == "true" ]]; then
        clean_docker_artifacts
    fi
    
    if [[ "$CLEAN_IDE" == "true" ]]; then
        clean_ide_artifacts
    fi
    
    if [[ "$CLEAN_SYSTEM" == "true" ]]; then
        clean_system_artifacts
    fi
    
    # Show summary
    show_summary
}

# Run main function
main "$@"
