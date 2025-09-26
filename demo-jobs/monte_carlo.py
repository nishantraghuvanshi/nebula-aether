#!/usr/bin/env python3
"""
Monte Carlo Pi Estimation - Task-Based Compute Benchmark
Uses parallel random number generation to estimate Pi value to target accuracy
Mac-compatible with configurable accuracy target and complexity
"""

import torch
import time
import argparse
import math

def main():
    parser = argparse.ArgumentParser(description='Monte Carlo Pi Estimation')
    parser.add_argument('--samples-per-round', type=int, default=100_000_000, help='Number of random samples per round')
    parser.add_argument('--device', type=str, default='auto', help='Device to use')
    parser.add_argument('--target-accuracy', type=float, default=99.5, help='Target accuracy percentage (e.g., 99.5 for 99.5%)')
    parser.add_argument('--complexity', type=int, default=4, help='Computational complexity multiplier')
    parser.add_argument('--max-rounds', type=int, default=50, help='Maximum number of rounds to prevent infinite loops')
    args = parser.parse_args()

    print(f"🎲 Starting Monte Carlo Pi Estimation")
    print(f"   Samples per round: {args.samples_per_round:,}")
    print(f"   Target accuracy: {args.target_accuracy}%")
    print(f"   Complexity: {args.complexity}x")
    print(f"   Max rounds: {args.max_rounds}")

    # Device selection with optimization
    if args.device == 'auto':
        if torch.cuda.is_available():
            device = torch.device('cuda')
            print(f"📱 Using CUDA GPU: {torch.cuda.get_device_name(0)}")
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device = torch.device('mps')
            print("🍎 Using Apple Silicon GPU (MPS)")
        else:
            device = torch.device('cpu')
            print("💻 Using CPU (multi-threaded)")
            # Enable multi-threading for CPU
            torch.set_num_threads(4)
    else:
        device = torch.device(args.device)
        print(f"📱 Using specified device: {device}")

    # Adaptive batch processing for memory efficiency
    if device.type == 'cuda':
        batch_size = min(args.samples_per_round, 15_000_000)  # GPU batch size
    elif device.type == 'mps':
        batch_size = min(args.samples_per_round, 7_500_000)   # MPS batch size
    else:
        batch_size = min(args.samples_per_round, 3_750_000)   # CPU batch size

    total_inside = 0
    total_processed = 0
    round_count = 0

    print(f"🔢 Processing in batches of {batch_size:,} samples")
    print(f"🎯 Will run multiple rounds until {args.target_accuracy}% accuracy is achieved")
    start_time = time.time()

    try:
        # Run until target accuracy is achieved
        while True:
            round_count += 1
            round_start = time.time()
            round_processed = 0
            round_inside = 0

            print(f"🔄 Starting round {round_count}...")

            # Process one round of samples
            current_samples = args.samples_per_round
            batch_count = 0

            while round_processed < current_samples:
                current_batch = min(batch_size, current_samples - round_processed)
                batch_count += 1

                # Generate random points in [0,1] x [0,1] square
                x = torch.rand(current_batch, device=device, dtype=torch.float32)
                y = torch.rand(current_batch, device=device, dtype=torch.float32)

                # Add computational complexity for longer runtime
                for complexity_iter in range(args.complexity):
                    # Use operations that preserve uniform distribution
                    temp_x = x * 2.0 - 1.0  # Scale to [-1,1]
                    temp_y = y * 2.0 - 1.0
                    
                    # Perform heavy computation without changing distribution
                    _ = torch.sqrt(temp_x * temp_x + temp_y * temp_y)  # Distance calculation
                    _ = torch.atan2(temp_y, temp_x)  # Angle calculation
                    
                    # Keep original uniform distribution intact
                    # x and y remain unchanged for the actual Monte Carlo calculation

                # Check which points fall inside unit circle
                # Distance from origin: sqrt(x^2 + y^2) <= 1
                # Optimized: x^2 + y^2 <= 1 (avoid sqrt)
                distances_squared = x*x + y*y
                inside_circle = distances_squared <= 1.0

                # Count points inside circle
                batch_inside = torch.sum(inside_circle).item()
                round_inside += batch_inside
                round_processed += current_batch
                total_inside += batch_inside
                total_processed += current_batch

                # Progress reporting every few batches
                if batch_count % 5 == 0:
                    elapsed = time.time() - start_time
                    samples_per_sec = total_processed / elapsed if elapsed > 0 else 0
                    current_pi_estimate = 4.0 * total_inside / total_processed
                    error = abs(current_pi_estimate - math.pi)

                    print(f"⚡ Round {round_count}, Batch {batch_count}: {round_processed:,}/{current_samples:,} "
                          f"({samples_per_sec:,.0f} samples/sec)")
                    print(f"🎯 Current π estimate: {current_pi_estimate:.6f} "
                          f"(error: {error:.6f})")

                # Cleanup batch data
                del x, y, distances_squared, inside_circle

                # Small delay for system stability
                time.sleep(0.01)

            round_time = time.time() - round_start
            elapsed_total = time.time() - start_time

            # Calculate current accuracy
            current_pi_estimate = 4.0 * total_inside / total_processed
            error = abs(current_pi_estimate - math.pi)
            accuracy_percent = (1 - error / math.pi) * 100

            print(f"✅ Round {round_count} completed in {round_time:.1f}s")
            print(f"   Round π estimate: {4.0 * round_inside / round_processed:.6f}")
            print(f"   Overall accuracy: {accuracy_percent:.4f}%")

            # Check if we've reached target accuracy
            if accuracy_percent >= args.target_accuracy:
                print(f"🎯 Target accuracy of {args.target_accuracy}% achieved! ({accuracy_percent:.4f}%)")
                break
            elif round_count >= args.max_rounds:
                print(f"⏰ Maximum rounds ({args.max_rounds}) reached. Stopping simulation.")
                print(f"   Current accuracy: {accuracy_percent:.4f}% (target: {args.target_accuracy}%)")
                break
            else:
                accuracy_gap = args.target_accuracy - accuracy_percent
                print(f"🔄 Continuing... Need {accuracy_gap:.4f}% more accuracy")

        # Synchronize GPU operations
        if device.type == 'cuda':
            torch.cuda.synchronize()

        total_time = time.time() - start_time

        # Final calculation
        pi_estimate = 4.0 * total_inside / total_processed
        error = abs(pi_estimate - math.pi)
        accuracy_percent = (1 - error / math.pi) * 100

        # Performance metrics
        samples_per_sec = total_processed / total_time
        throughput_gbps = (total_processed * 8) / total_time / 1e9  # 8 bytes per sample (2 floats)
        effective_tflops = (total_processed * args.complexity * 10) / total_time / 1e12  # Rough FLOPS estimate

        print(f"\n🎉 Monte Carlo simulation completed!")
        print(f"⏱️ Total time: {total_time:.2f} seconds")
        print(f"🔄 Rounds completed: {round_count}")
        print(f"🔢 Samples processed: {total_processed:,}")
        print(f"⚡ Performance: {samples_per_sec:,.0f} samples/sec")
        print(f"📊 Memory throughput: {throughput_gbps:.2f} GB/s")
        print(f"🚀 Compute performance: ~{effective_tflops:.3f} TFLOPS")
        print(f"\n🎯 Results:")
        print(f"   π estimate: {pi_estimate:.8f}")
        print(f"   Actual π:   {math.pi:.8f}")
        print(f"   Error:      {error:.8f}")
        print(f"   Accuracy:   {accuracy_percent:.4f}%")

        # Memory cleanup
        if device.type == 'cuda':
            memory_allocated = torch.cuda.memory_allocated() / 1024**2
            print(f"💾 Peak GPU memory: {memory_allocated:.1f} MB")
            torch.cuda.empty_cache()
        elif device.type == 'mps':
            print(f"🍎 MPS compute completed")

    except torch.cuda.OutOfMemoryError:
        print("❌ GPU out of memory! Try reducing --samples parameter")
        return 1
    except Exception as e:
        print(f"❌ Error during Monte Carlo simulation: {e}")
        return 1

    print(f"✨ Monte Carlo Pi Estimation completed successfully!")
    print(f"🔥 Total compute time: {total_time:.1f} seconds across {round_count} rounds")
    print(f"📊 Final accuracy achieved: {accuracy_percent:.2f}%")
    return 0

if __name__ == "__main__":
    try:
        exit(main())
    except KeyboardInterrupt:
        print("\n⏹️  Monte Carlo simulation interrupted by user")
        exit(0)
    except Exception as e:
        print(f"\n❌ Monte Carlo simulation failed: {e}")
        exit(1)