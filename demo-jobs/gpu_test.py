#!/usr/bin/env python3
"""
Simple GPU utilization test to verify device usage
"""
import torch
import time
import argparse

def main():
    parser = argparse.ArgumentParser(description='GPU Utilization Test')
    parser.add_argument('--device', type=str, default='auto', help='Device to use')
    parser.add_argument('--duration', type=int, default=30, help='Test duration in seconds')
    parser.add_argument('--matrix-size', type=int, default=2048, help='Matrix size for computation')
    args = parser.parse_args()

    print("🧪 GPU Utilization Test")
    print(f"   Duration: {args.duration} seconds")
    print(f"   Matrix size: {args.matrix_size}x{args.matrix_size}")

    # Device selection
    if args.device == 'auto':
        if torch.cuda.is_available():
            device = torch.device('cuda')
            print(f"📱 Using CUDA GPU: {torch.cuda.get_device_name(0)}")
            print(f"   CUDA Version: {torch.version.cuda}")
            print(f"   CUDA Compute Capability: {torch.cuda.get_device_capability(0)}")
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device = torch.device('mps')
            print("🍎 Using Apple Silicon GPU (MPS)")
        else:
            device = torch.device('cpu')
            print("💻 Using CPU")
    else:
        device = torch.device(args.device)
        print(f"📱 Using specified device: {device}")

    # Create large matrices on the selected device
    print(f"🚀 Creating {args.matrix_size}x{args.matrix_size} matrices on {device}...")

    try:
        # Create matrices that will actually use significant GPU resources
        A = torch.randn(args.matrix_size, args.matrix_size, device=device, dtype=torch.float32)
        B = torch.randn(args.matrix_size, args.matrix_size, device=device, dtype=torch.float32)

        print("✅ Matrices created successfully")
        print(f"💾 Memory per matrix: {A.element_size() * A.nelement() / 1024**2:.1f} MB")

        start_time = time.time()
        operations = 0

        print(f"🔥 Starting intensive computation for {args.duration} seconds...")

        while time.time() - start_time < args.duration:
            # Intensive matrix operations
            C = torch.matmul(A, B)  # Matrix multiplication
            C = torch.sin(C)        # Trigonometric operations
            C = torch.relu(C)       # Activation function
            A = torch.transpose(C, 0, 1)  # Memory reorganization

            operations += 1

            # Progress update every 5 seconds
            elapsed = time.time() - start_time
            if operations % 10 == 0:  # Every 10 operations
                print(f"⚡ {elapsed:.1f}s: Completed {operations} operations ({operations/elapsed:.1f} ops/sec)")

                # Show memory usage if CUDA
                if device.type == 'cuda':
                    memory_allocated = torch.cuda.memory_allocated() / 1024**2
                    print(f"💾 GPU Memory allocated: {memory_allocated:.1f} MB")

        total_time = time.time() - start_time
        print(f"\n🎉 Test completed!")
        print(f"⏱️ Total time: {total_time:.2f} seconds")
        print(f"🔢 Total operations: {operations}")
        print(f"⚡ Operations per second: {operations/total_time:.2f}")

        # Final memory cleanup and stats
        if device.type == 'cuda':
            torch.cuda.synchronize()
            memory_allocated = torch.cuda.memory_allocated() / 1024**2
            peak_memory = torch.cuda.max_memory_allocated() / 1024**2
            print(f"💾 Final GPU Memory - Current: {memory_allocated:.1f} MB, Peak: {peak_memory:.1f} MB")
            torch.cuda.empty_cache()

            # GPU utilization info
            print(f"🚀 GPU should show high utilization during this test!")
            print(f"   Check nvidia-smi or GPU monitoring tools")

        elif device.type == 'mps':
            print("🍎 MPS intensive computation completed")
            print("   Check Activity Monitor for GPU usage")

    except Exception as e:
        print(f"❌ Error during GPU test: {e}")
        if "out of memory" in str(e).lower():
            print(f"💡 Try reducing --matrix-size (current: {args.matrix_size})")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())