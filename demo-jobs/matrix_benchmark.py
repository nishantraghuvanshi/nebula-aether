#!/usr/bin/env python3
"""
Matrix Multiplication Benchmark - Pure GPU Compute Stress Test
Performs large matrix operations to stress GPU compute units
"""

import torch
import time
import argparse
import gc

def main():
    parser = argparse.ArgumentParser(description='Matrix Multiplication Benchmark')
    parser.add_argument('--size', type=int, default=4096, help='Matrix size (NxN)')
    parser.add_argument('--iterations', type=int, default=500, help='Number of iterations')
    parser.add_argument('--device', type=str, default='auto', help='Device to use')
    args = parser.parse_args()

    print(f"🧮 Starting Matrix Benchmark - Size: {args.size}x{args.size}, Iterations: {args.iterations}")

    # Device selection
    if args.device == 'auto':
        if torch.cuda.is_available():
            device = torch.device('cuda')
            print(f"📱 Using CUDA GPU: {torch.cuda.get_device_name(0)}")
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device = torch.device('mps')
            print("🍎 Using Apple Silicon GPU (MPS)")
        else:
            device = torch.device('cpu')
            print("💻 Using CPU")
    else:
        device = torch.device(args.device)

    # Calculate memory requirements
    matrix_memory_gb = (args.size * args.size * 4 * 3) / (1024**3)  # 3 matrices, 4 bytes per float32
    print(f"💾 Estimated GPU memory usage: {matrix_memory_gb:.2f}GB")

    try:
        # Create large matrices on GPU
        print("🏗️ Allocating matrices on GPU...")
        A = torch.randn(args.size, args.size, device=device, dtype=torch.float32)
        B = torch.randn(args.size, args.size, device=device, dtype=torch.float32)

        # Warm up GPU
        print("🔥 Warming up GPU...")
        for _ in range(5):
            _ = torch.matmul(A, B)
            if device.type == 'cuda':
                torch.cuda.synchronize()

        print("🚀 Starting benchmark...")
        start_time = time.time()

        # Main computation loop
        for i in range(args.iterations):
            # Matrix multiplication (most compute-intensive operation)
            C = torch.matmul(A, B)

            # Add some variety to prevent optimization
            if i % 10 == 0:
                A = A + 0.001 * torch.randn_like(A)
                B = B + 0.001 * torch.randn_like(B)

            # Matrix transpose and operations
            if i % 5 == 0:
                C = torch.matmul(C.T, A)

            # Ensure GPU operations complete
            if device.type == 'cuda':
                torch.cuda.synchronize()

            # Progress indicator
            if (i + 1) % 50 == 0:
                elapsed = time.time() - start_time
                ops_per_sec = (i + 1) / elapsed
                print(f"⚡ Iteration {i+1}/{args.iterations} ({ops_per_sec:.1f} ops/sec)")

        # Synchronize and measure final time
        if device.type == 'cuda':
            torch.cuda.synchronize()

        total_time = time.time() - start_time
        ops_per_sec = args.iterations / total_time

        # Calculate performance metrics
        flops_per_op = 2 * args.size**3  # Approximate FLOPs for matrix multiplication
        total_flops = flops_per_op * args.iterations
        gflops_per_sec = (total_flops / total_time) / 1e9

        print(f"🎉 Benchmark completed!")
        print(f"⏱️  Total time: {total_time:.2f} seconds")
        print(f"🔢 Operations per second: {ops_per_sec:.1f}")
        print(f"⚡ Performance: {gflops_per_sec:.1f} GFLOPS")

        # Memory info
        if device.type == 'cuda':
            memory_allocated = torch.cuda.memory_allocated() / 1024**3
            memory_reserved = torch.cuda.memory_reserved() / 1024**3
            print(f"💾 GPU Memory - Allocated: {memory_allocated:.2f}GB, Reserved: {memory_reserved:.2f}GB")

    except torch.cuda.OutOfMemoryError:
        print("❌ GPU out of memory! Try reducing --size parameter")
        return 1
    except Exception as e:
        print(f"❌ Error during benchmark: {e}")
        return 1
    finally:
        # Cleanup
        if device.type == 'cuda':
            torch.cuda.empty_cache()
        gc.collect()
        print("🧹 Memory cleanup completed")

    print("✨ Matrix benchmark job completed successfully!")
    return 0

if __name__ == "__main__":
    exit(main())