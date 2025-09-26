#!/usr/bin/env python3
"""
Video Encoding Benchmark - H.264/H.265 Simulation
Simulates video transcoding workload using parallel matrix operations
Mac-compatible with CUDA/MPS acceleration
"""

import torch
import torch.nn.functional as F
import time
import argparse
import math

def simulate_dct_transform(frames, device):
    """
    Simulate DCT (Discrete Cosine Transform) used in video compression
    """
    # Create DCT basis matrix
    N = frames.shape[-1]
    dct_matrix = torch.zeros(N, N, device=device)

    for k in range(N):
        for n in range(N):
            if k == 0:
                dct_matrix[k, n] = math.sqrt(1/N)
            else:
                dct_matrix[k, n] = math.sqrt(2/N) * math.cos((2*n + 1) * k * math.pi / (2*N))

    # Apply DCT transform
    transformed = torch.matmul(torch.matmul(dct_matrix, frames), dct_matrix.T)
    return transformed

def simulate_quantization(coeffs, quality_factor):
    """
    Simulate quantization step in video encoding
    """
    # Standard JPEG quantization matrix (8x8)
    quant_matrix = torch.tensor([
        [16, 11, 10, 16, 24, 40, 51, 61],
        [12, 12, 14, 19, 26, 58, 60, 55],
        [14, 13, 16, 24, 40, 57, 69, 56],
        [14, 17, 22, 29, 51, 87, 80, 62],
        [18, 22, 37, 56, 68, 109, 103, 77],
        [24, 35, 55, 64, 81, 104, 113, 92],
        [49, 64, 78, 87, 103, 121, 120, 101],
        [72, 92, 95, 98, 112, 100, 103, 99]
    ], dtype=torch.float32, device=coeffs.device)

    # Scale quantization matrix by quality factor
    quant_matrix = quant_matrix * (50.0 / quality_factor) if quality_factor < 50 else quant_matrix * (2.0 - quality_factor / 50.0)

    # Apply quantization
    quantized = torch.round(coeffs / quant_matrix.unsqueeze(0))
    return quantized

def simulate_motion_estimation(current_frame, reference_frame, block_size=16):
    """
    Simulate motion estimation for video compression
    """
    batch_size, height, width = current_frame.shape

    # Simplified motion compensation - just return a warped version of the reference frame
    # Create a small random displacement for the entire frame
    displacement_h = torch.randint(-8, 9, (batch_size,), device=current_frame.device, dtype=torch.float32)
    displacement_w = torch.randint(-8, 9, (batch_size,), device=current_frame.device, dtype=torch.float32)

    # Create a simple compensated frame by shifting the reference frame slightly
    compensated = torch.zeros_like(current_frame)

    for b in range(batch_size):
        # Simple translation compensation
        h_shift = int(displacement_h[b].item())
        w_shift = int(displacement_w[b].item())

        # Calculate valid region after shift
        h_start = max(0, h_shift)
        h_end = min(height, height + h_shift)
        w_start = max(0, w_shift)
        w_end = min(width, width + w_shift)

        ref_h_start = max(0, -h_shift)
        ref_h_end = ref_h_start + (h_end - h_start)
        ref_w_start = max(0, -w_shift)
        ref_w_end = ref_w_start + (w_end - w_start)

        # Copy the shifted region
        if h_end > h_start and w_end > w_start:
            compensated[b, h_start:h_end, w_start:w_end] = reference_frame[b, ref_h_start:ref_h_end, ref_w_start:ref_w_end]

    # Create dummy motion vectors for return value
    num_blocks_h = height // block_size
    num_blocks_w = width // block_size
    motion_vectors = torch.stack([displacement_w.unsqueeze(-1).expand(-1, num_blocks_h * num_blocks_w),
                                  displacement_h.unsqueeze(-1).expand(-1, num_blocks_h * num_blocks_w)], dim=-1)
    motion_vectors = motion_vectors.view(batch_size, num_blocks_h, num_blocks_w, 2)

    return compensated, motion_vectors

def main():
    parser = argparse.ArgumentParser(description='Video Encoding Benchmark')
    parser.add_argument('--frames', type=int, default=1000, help='Number of frames to encode')
    parser.add_argument('--resolution', type=str, default='1080p', help='Video resolution (720p, 1080p, 4k)')
    parser.add_argument('--device', type=str, default='auto', help='Device to use')
    parser.add_argument('--quality', type=int, default=23, help='Encoding quality factor (1-51, lower is better)')
    parser.add_argument('--batch-size', type=int, default=4, help='Number of frames to process simultaneously')
    args = parser.parse_args()

    print(f"🎬 Starting Video Encoding Benchmark")
    print(f"   Frames to encode: {args.frames}")
    print(f"   Resolution: {args.resolution}")
    print(f"   Quality factor: {args.quality}/51")
    print(f"   Batch size: {args.batch_size}")

    # Resolution mapping
    resolution_map = {
        '720p': (1280, 720),
        '1080p': (1920, 1080),
        '4k': (3840, 2160)
    }

    if args.resolution not in resolution_map:
        print(f"❌ Unsupported resolution: {args.resolution}")
        return 1

    width, height = resolution_map[args.resolution]
    print(f"   Frame size: {width}x{height}")

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
            print("💻 Using CPU (multi-threaded)")
            torch.set_num_threads(4)
    else:
        device = torch.device(args.device)
        print(f"📱 Using specified device: {device}")

    # Memory estimation
    frame_size_mb = (width * height * 4) / (1024 * 1024)  # RGBA float32
    total_memory_mb = frame_size_mb * args.batch_size * 3  # Current + reference + working
    print(f"💾 Estimated memory usage: {total_memory_mb:.1f} MB per batch")

    try:
        frames_processed = 0
        total_bytes = 0
        start_time = time.time()

        # Initialize reference frame (simulating I-frame)
        reference_frame = torch.randn(args.batch_size, height, width, device=device, dtype=torch.float32)

        print(f"🚀 Starting encoding process...")

        # Add timeout safety
        max_runtime = 60  # 1 minute max
        timeout_start = time.time()

        while frames_processed < args.frames:
            # Safety timeout check
            if time.time() - timeout_start > max_runtime:
                print(f"⏰ Video encoding timeout after {max_runtime}s - stopping early")
                break
            batch_start = time.time()

            # Determine current batch size (handle remainder)
            current_batch_size = min(args.batch_size, args.frames - frames_processed)

            # Generate current frame batch (simulating P-frames)
            current_frames = torch.randn(current_batch_size, height, width, device=device, dtype=torch.float32)

            # Step 1: Motion Estimation and Compensation
            compensated_frames, motion_vectors = simulate_motion_estimation(
                current_frames[:current_batch_size],
                reference_frame[:current_batch_size]
            )

            # Step 2: Residual calculation
            residual = current_frames - compensated_frames

            # Step 3: Transform coding (DCT) - process in 8x8 blocks
            block_size = 8
            encoded_blocks = []

            # Process frames in 8x8 blocks across the entire frame
            for h in range(0, height, block_size):
                for w in range(0, width, block_size):
                    # Extract 8x8 blocks from the frame
                    h_end = min(h + block_size, height)
                    w_end = min(w + block_size, width)

                    block = residual[:current_batch_size, h:h_end, w:w_end]

                    # Pad to exact block size if necessary
                    if block.shape[1] < block_size or block.shape[2] < block_size:
                        padded_block = torch.zeros(current_batch_size, block_size, block_size, device=device)
                        padded_block[:, :block.shape[1], :block.shape[2]] = block
                        block = padded_block

                    # Apply DCT transform
                    dct_coeffs = simulate_dct_transform(block, device)

                    # Quantization
                    quantized = simulate_quantization(dct_coeffs, args.quality)
                    encoded_blocks.append(quantized)

            # Step 4: Entropy coding simulation (simple bit counting)
            total_coeffs = sum(block.numel() for block in encoded_blocks)
            non_zero_coeffs = sum(torch.count_nonzero(block) for block in encoded_blocks)
            compression_ratio = total_coeffs / max(non_zero_coeffs, 1)

            # Calculate encoded size (simulation)
            original_size = current_batch_size * width * height * 4  # bytes
            encoded_size = int(original_size / compression_ratio)
            total_bytes += encoded_size

            # Update reference frame for next iteration
            reference_frame[:current_batch_size] = current_frames

            frames_processed += current_batch_size
            batch_time = time.time() - batch_start

            # Progress reporting
            if frames_processed % (args.batch_size * 10) == 0 or frames_processed >= args.frames:
                elapsed = time.time() - start_time
                fps = frames_processed / elapsed if elapsed > 0 else 0
                mbps = (total_bytes / elapsed) / (1024 * 1024) if elapsed > 0 else 0

                print(f"⚡ Encoded: {frames_processed}/{args.frames} frames "
                      f"({fps:.1f} FPS, {mbps:.1f} MB/s)")
                print(f"   Compression: {compression_ratio:.2f}x, "
                      f"Batch time: {batch_time:.2f}s")

            # Small delay for system stability
            time.sleep(0.01)

        # Synchronize GPU operations
        if device.type == 'cuda':
            torch.cuda.synchronize()

        total_time = time.time() - start_time

        # Final statistics
        avg_fps = frames_processed / total_time
        total_pixels = frames_processed * width * height
        pixels_per_sec = total_pixels / total_time
        throughput_mbps = (total_bytes / total_time) / (1024 * 1024)
        original_size_gb = (frames_processed * width * height * 4) / (1024 ** 3)
        compressed_size_gb = total_bytes / (1024 ** 3)
        overall_compression = original_size_gb / compressed_size_gb if compressed_size_gb > 0 else 1.0

        print(f"\n🎉 Video encoding completed!")
        print(f"⏱️ Total time: {total_time:.2f} seconds")
        print(f"📊 Performance:")
        print(f"   Frames encoded: {frames_processed}")
        print(f"   Average FPS: {avg_fps:.1f}")
        print(f"   Pixels/second: {pixels_per_sec:,.0f}")
        print(f"   Throughput: {throughput_mbps:.2f} MB/s")
        print(f"\n🗜️ Compression Results:")
        print(f"   Original size: {original_size_gb:.2f} GB")
        print(f"   Compressed size: {compressed_size_gb:.2f} GB")
        print(f"   Compression ratio: {overall_compression:.2f}x")
        print(f"   Quality factor: {args.quality}/51")

        # Memory cleanup
        if device.type == 'cuda':
            memory_allocated = torch.cuda.memory_allocated() / 1024**2
            peak_memory = torch.cuda.max_memory_allocated() / 1024**2
            print(f"💾 GPU Memory - Current: {memory_allocated:.1f} MB, Peak: {peak_memory:.1f} MB")
            torch.cuda.empty_cache()
        elif device.type == 'mps':
            print("🍎 MPS encoding completed")

    except torch.cuda.OutOfMemoryError:
        print("❌ GPU out of memory! Try reducing --batch-size or --resolution")
        return 1
    except Exception as e:
        print(f"❌ Error during video encoding: {e}")
        return 1

    print(f"✨ Video encoding benchmark completed successfully!")
    print(f"🎬 Processed {frames_processed} frames at {args.resolution} resolution")
    return 0

if __name__ == "__main__":
    try:
        exit(main())
    except KeyboardInterrupt:
        print("\n⏹️  Video encoding interrupted by user")
        exit(0)
    except Exception as e:
        print(f"\n❌ Video encoding failed: {e}")
        exit(1)