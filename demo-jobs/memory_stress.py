#!/usr/bin/env python3
"""
Memory Stress Test - GPU/CPU Compatible
Allocates and manipulates memory to test bandwidth and capacity
Mac-compatible with automatic device detection and safety limits
"""

import torch
import time
import argparse
import gc
import signal
import sys

# Global flag for graceful shutdown
shutdown_requested = False

def signal_handler(signum, frame):
    global shutdown_requested
    print(f"\n🛑 Signal {signum} received. Initiating graceful shutdown...")
    shutdown_requested = True

def get_available_memory(device):
    """Get available memory for the device"""
    if device.type == 'cuda':
        total_memory = torch.cuda.get_device_properties(0).total_memory
        allocated_memory = torch.cuda.memory_allocated()
        return (total_memory - allocated_memory) / 1024**3
    elif device.type == 'mps':
        # For MPS, use conservative estimate (assume 8GB unified memory)
        return 6.0  # Conservative limit for Mac
    else:
        # For CPU, use conservative estimate
        return 4.0

def main():
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    parser = argparse.ArgumentParser(description='Memory Stress Test')
    parser.add_argument('--memory-gb', type=float, default=3.0, help='Memory to allocate in GB')
    parser.add_argument('--duration', type=int, default=60, help='Test duration in seconds')
    parser.add_argument('--device', type=str, default='auto', help='Device to use')
    parser.add_argument('--safety-limit', type=float, default=0.8, help='Safety factor (0.5-0.9)')
    args = parser.parse_args()

    print(f"💾 Starting Memory Stress Test")
    print(f"   Target: {args.memory_gb}GB, Duration: {args.duration}s")
    print(f"   Safety Factor: {args.safety_limit}")

    # Device selection with safety checks
    if args.device == 'auto':
        if torch.cuda.is_available():
            device = torch.device('cuda')
            print(f"📱 Using CUDA GPU: {torch.cuda.get_device_name(0)}")
            total_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            print(f"📊 Total GPU Memory: {total_memory:.1f}GB")
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device = torch.device('mps')
            print("🍎 Using Apple Silicon GPU (MPS) - Unified Memory")
        else:
            device = torch.device('cpu')
            print("💻 Using CPU (System RAM)")
    else:
        device = torch.device(args.device)
        print(f"📱 Using specified device: {device}")

    # Safety check - limit memory allocation
    available_memory = get_available_memory(device)
    safe_memory = available_memory * args.safety_limit

    if args.memory_gb > safe_memory:
        print(f"⚠️  Requested {args.memory_gb}GB exceeds safe limit of {safe_memory:.1f}GB")
        print(f"   Adjusting to safe allocation: {safe_memory:.1f}GB")
        args.memory_gb = safe_memory

    print(f"📊 Available Memory: {available_memory:.1f}GB")
    print(f"🛡️  Safe Allocation: {args.memory_gb:.1f}GB")

    try:
        # Calculate tensor size to allocate target memory
        bytes_per_float32 = 4
        target_bytes = int(args.memory_gb * 1024**3)
        elements_needed = target_bytes // bytes_per_float32

        # Create multiple tensors in smaller chunks for safety
        num_chunks = 15  # Reduced chunks for less intensity
        chunk_size = elements_needed // num_chunks
        tensors = []

        print(f"🏗️ Allocating {args.memory_gb:.1f}GB of memory in {num_chunks} chunks...")
        print(f"   Chunk size: {chunk_size:,} elements ({chunk_size*4/1024**2:.1f}MB each)")

        for i in range(num_chunks):
            if shutdown_requested:
                print("🛑 Shutdown requested during memory allocation")
                break

            try:
                print(f"⚡ Allocating chunk {i+1}/{num_chunks}...", end="")
                tensor = torch.randn(chunk_size, device=device, dtype=torch.float32)
                tensors.append(tensor)

                if device.type == 'cuda':
                    allocated = torch.cuda.memory_allocated() / 1024**3
                    print(f" ✅ {allocated:.2f}GB allocated")
                else:
                    print(f" ✅ Chunk {i+1} allocated")

                # Small delay between allocations for stability
                time.sleep(0.1)

            except (torch.cuda.OutOfMemoryError, RuntimeError) as e:
                print(f" ⚠️  Allocation failed at chunk {i+1}, stopping here")
                break

        if len(tensors) == 0:
            print("❌ No memory could be allocated!")
            return 1

        actual_allocation = len(tensors) * chunk_size * 4 / 1024**3
        print(f"✅ Memory allocation completed!")
        print(f"📊 Successfully allocated: {actual_allocation:.2f}GB ({len(tensors)} chunks)")

        if device.type == 'cuda':
            allocated_gb = torch.cuda.memory_allocated() / 1024**3
            reserved_gb = torch.cuda.memory_reserved() / 1024**3
            print(f"📊 CUDA Memory - Allocated: {allocated_gb:.2f}GB, Reserved: {reserved_gb:.2f}GB")
        elif device.type == 'mps':
            print(f"🍎 MPS Memory - Using unified memory system")

        # Memory stress operations
        print(f"🔄 Starting memory operations for {args.duration} seconds...")
        start_time = time.time()
        operation_count = 0
        last_progress_time = 0

        while time.time() - start_time < args.duration and not shutdown_requested:
            try:
                # Memory bandwidth stress - lighter operations for stability
                for i in range(min(len(tensors), 3)):  # Only operate on first 3 chunks at a time
                    if shutdown_requested:
                        print("🛑 Shutdown requested during memory operations")
                        break

                    # Lighter in-place operations
                    tensors[i].add_(0.01)  # Slightly modify values
                    if operation_count % 50 == 0:
                        tensors[i].mul_(0.999)  # Occasional scaling

                    operation_count += 1

                # Check for shutdown between operations
                if shutdown_requested:
                    print("🛑 Shutdown requested, stopping memory test")
                    break

                # Progress update every 5 seconds
                elapsed = time.time() - start_time
                if elapsed - last_progress_time >= 5.0:
                    ops_per_sec = operation_count / elapsed if elapsed > 0 else 0
                    print(f"⏱️ {elapsed:.0f}s elapsed, {operation_count} operations ({ops_per_sec:.0f} ops/sec)")
                    last_progress_time = elapsed

                # Small delay for system stability
                time.sleep(0.01)

            except (torch.cuda.OutOfMemoryError, RuntimeError) as e:
                print(f"⚠️  Memory operation failed: {e}")
                break

        total_time = time.time() - start_time
        ops_per_sec = operation_count / total_time

        print(f"🎉 Memory stress test completed!")
        print(f"⏱️ Duration: {total_time:.1f} seconds")
        print(f"🔢 Operations: {operation_count} ({ops_per_sec:.0f} ops/sec)")

        # Final memory stats
        if device.type == 'cuda':
            final_allocated = torch.cuda.memory_allocated() / 1024**3
            final_reserved = torch.cuda.memory_reserved() / 1024**3
            print(f"📊 Final memory - Allocated: {final_allocated:.2f}GB, Reserved: {final_reserved:.2f}GB")

    except torch.cuda.OutOfMemoryError:
        print("❌ GPU out of memory! Try reducing --memory-gb parameter")
        return 1
    except RuntimeError as e:
        if "out of memory" in str(e).lower():
            print(f"❌ Device out of memory: {e}")
            print("💡 Try reducing --memory-gb or using --safety-limit 0.5")
        else:
            print(f"❌ Runtime error: {e}")
        return 1
    except Exception as e:
        print(f"❌ Error during memory stress test: {e}")
        return 1
    finally:
        # Thorough cleanup
        print("🧹 Cleaning up memory...")
        if 'tensors' in locals():
            tensor_count = len(tensors)
            del tensors
            print(f"   Deleted {tensor_count} tensors")

        if device.type == 'cuda':
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            final_allocated = torch.cuda.memory_allocated() / 1024**3
            print(f"   CUDA memory after cleanup: {final_allocated:.2f}GB")
        elif device.type == 'mps':
            # MPS doesn't have explicit cache clearing
            pass

        gc.collect()
        print("✨ Memory cleanup completed")

    print("✅ Memory stress test completed successfully!")
    return 0

if __name__ == "__main__":
    exit(main())