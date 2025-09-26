#!/usr/bin/env python3
"""
Ray Tracing Benchmark - Path Tracing Simulation
Simulates modern ray tracing with reflections, shadows, and global illumination
Mac-compatible with CUDA/MPS acceleration
"""

import torch
import math
import time
import argparse

class Sphere:
    def __init__(self, center, radius, material_type, color, device):
        self.center = torch.tensor(center, device=device, dtype=torch.float32)
        self.radius = radius
        self.material_type = material_type  # 0: diffuse, 1: metal, 2: glass
        self.color = torch.tensor(color, device=device, dtype=torch.float32)

def ray_sphere_intersection(ray_origin, ray_direction, sphere_center, sphere_radius):
    """
    Calculate ray-sphere intersection using quadratic formula
    """
    oc = ray_origin - sphere_center.unsqueeze(0)
    a = torch.sum(ray_direction * ray_direction, dim=-1)
    b = 2.0 * torch.sum(oc * ray_direction, dim=-1)
    c = torch.sum(oc * oc, dim=-1) - sphere_radius * sphere_radius

    discriminant = b * b - 4 * a * c

    # Check for intersection
    hit = discriminant >= 0

    # Calculate intersection points
    sqrt_discriminant = torch.sqrt(torch.clamp(discriminant, min=0))
    t1 = (-b - sqrt_discriminant) / (2 * a)
    t2 = (-b + sqrt_discriminant) / (2 * a)

    # Use closest positive intersection
    t = torch.where(t1 > 0.001, t1, t2)
    t = torch.where(hit & (t > 0.001), t, torch.full_like(t, float('inf')))

    return t, hit

def fresnel_reflectance(cos_theta, ref_idx):
    """
    Calculate Fresnel reflectance using Schlick's approximation
    """
    r0 = ((1 - ref_idx) / (1 + ref_idx)) ** 2
    return r0 + (1 - r0) * ((1 - cos_theta) ** 5)

def random_unit_vector(shape, device):
    """
    Generate random unit vectors for diffuse reflection
    """
    # Generate random points in unit sphere using rejection sampling
    # Convert tuple shape to list for concatenation
    if isinstance(shape, tuple):
        shape = list(shape)

    random_vec = 2.0 * torch.rand(shape + [3], device=device) - 1.0
    length_squared = torch.sum(random_vec * random_vec, dim=-1, keepdim=True)

    # Simple normalization (avoiding while loop for efficiency)
    return random_vec / torch.sqrt(torch.clamp(length_squared, min=0.001))

def trace_ray(ray_origin, ray_direction, spheres, depth, max_depth, device):
    """
    Recursive ray tracing function with depth limiting for performance
    """
    if depth >= max_depth:
        # Return sky color (gradient)
        t = 0.5 * (ray_direction[..., 1] + 1.0)
        sky_color = (1.0 - t).unsqueeze(-1) * torch.tensor([1.0, 1.0, 1.0], device=device) + \
                   t.unsqueeze(-1) * torch.tensor([0.5, 0.7, 1.0], device=device)
        return sky_color

    closest_t = torch.full(ray_origin.shape[:-1], float('inf'), device=device)
    hit_sphere_idx = torch.full(ray_origin.shape[:-1], -1, device=device, dtype=torch.long)

    # Test intersection with all spheres
    for i, sphere in enumerate(spheres):
        t, hit = ray_sphere_intersection(ray_origin, ray_direction, sphere.center, sphere.radius)

        # Update closest intersection
        closer = hit & (t < closest_t)
        closest_t = torch.where(closer, t, closest_t)
        hit_sphere_idx = torch.where(closer, i, hit_sphere_idx)

    # Check if ray hit anything
    ray_hit = closest_t < float('inf')

    if not torch.any(ray_hit):
        # No hit, return sky color
        t = 0.5 * (ray_direction[..., 1] + 1.0)
        sky_color = (1.0 - t).unsqueeze(-1) * torch.tensor([1.0, 1.0, 1.0], device=device) + \
                   t.unsqueeze(-1) * torch.tensor([0.5, 0.7, 1.0], device=device)
        return sky_color

    # Calculate hit point and normal
    hit_point = ray_origin + closest_t.unsqueeze(-1) * ray_direction

    # Get material properties of hit sphere
    final_color = torch.zeros(ray_origin.shape[:-1] + (3,), device=device)

    for i, sphere in enumerate(spheres):
        sphere_mask = (hit_sphere_idx == i) & ray_hit
        if not torch.any(sphere_mask):
            continue

        # Calculate surface normal
        normal = (hit_point - sphere.center.unsqueeze(0)) / sphere.radius

        # Ensure normal points toward ray origin
        normal = torch.where((torch.sum(ray_direction * normal, dim=-1, keepdim=True) > 0),
                           -normal, normal)

        if sphere.material_type == 0:  # Diffuse material
            # Lambertian reflection
            target = hit_point + normal + random_unit_vector(hit_point.shape[:-1], device)
            scattered_direction = target - hit_point

            # Recursive ray trace
            scattered_color = trace_ray(hit_point, scattered_direction, spheres, depth + 1, max_depth, device)
            material_color = 0.5 * scattered_color * sphere.color.unsqueeze(0)

        elif sphere.material_type == 1:  # Metal material
            # Perfect reflection
            reflected = ray_direction - 2 * torch.sum(ray_direction * normal, dim=-1, keepdim=True) * normal

            # Add some roughness
            fuzz = 0.1
            reflected = reflected + fuzz * random_unit_vector(reflected.shape[:-1], device)

            # Recursive ray trace
            scattered_color = trace_ray(hit_point, reflected, spheres, depth + 1, max_depth, device)
            material_color = scattered_color * sphere.color.unsqueeze(0)

        else:  # Glass material
            ref_idx = 1.5
            cos_theta = torch.min(-torch.sum(ray_direction * normal, dim=-1),
                                torch.ones_like(closest_t))

            reflect_prob = fresnel_reflectance(cos_theta, ref_idx)

            # Simplified: always reflect for glass (proper refraction is complex)
            reflected = ray_direction - 2 * torch.sum(ray_direction * normal, dim=-1, keepdim=True) * normal
            scattered_color = trace_ray(hit_point, reflected, spheres, depth + 1, max_depth, device)
            material_color = scattered_color

        # Apply material color where this sphere was hit
        final_color = torch.where(sphere_mask.unsqueeze(-1), material_color, final_color)

    return final_color

def setup_scene(device):
    """
    Create a simple scene with multiple spheres
    """
    spheres = [
        # Ground sphere (large diffuse)
        Sphere([0, -100.5, -1], 100, 0, [0.5, 0.5, 0.5], device),

        # Center sphere (glass)
        Sphere([0, 0, -1], 0.5, 2, [1.0, 1.0, 1.0], device),

        # Left sphere (diffuse)
        Sphere([-1, 0, -1], 0.5, 0, [0.1, 0.2, 0.5], device),

        # Right sphere (metal)
        Sphere([1, 0, -1], 0.5, 1, [0.8, 0.6, 0.2], device),

        # Small spheres
        Sphere([-0.5, 0.5, -0.5], 0.2, 0, [0.8, 0.2, 0.2], device),
        Sphere([0.5, 0.5, -0.5], 0.2, 1, [0.2, 0.8, 0.2], device),
    ]

    return spheres

def main():
    parser = argparse.ArgumentParser(description='Ray Tracing Benchmark')
    parser.add_argument('--width', type=int, default=800, help='Image width in pixels')
    parser.add_argument('--height', type=int, default=600, help='Image height in pixels')
    parser.add_argument('--samples', type=int, default=10, help='Maximum samples per pixel')
    parser.add_argument('--max-depth', type=int, default=3, help='Maximum ray bounce depth')
    parser.add_argument('--device', type=str, default='auto', help='Device to use')
    parser.add_argument('--batch-size', type=int, default=64, help='Rays to trace per batch')
    parser.add_argument('--quality-target', type=float, default=0.95, help='Quality convergence target (0-1)')
    parser.add_argument('--min-samples', type=int, default=5, help='Minimum samples before checking convergence')
    parser.add_argument('--max-runtime', type=int, default=60, help='Maximum runtime in seconds')
    args = parser.parse_args()

    print(f"🌟 Starting Ray Tracing Benchmark")
    print(f"   Resolution: {args.width}x{args.height}")
    print(f"   Max samples per pixel: {args.samples}")
    print(f"   Quality target: {args.quality_target:.1%}")
    print(f"   Min samples: {args.min_samples}")
    print(f"   Max runtime: {args.max_runtime}s")
    print(f"   Max ray depth: {args.max_depth}")
    print(f"   Batch size: {args.batch_size}")

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
    total_pixels = args.width * args.height
    total_rays = total_pixels * args.samples
    memory_per_ray = 12 * 4  # 3 floats for origin + 3 for direction + 3 for color + 3 extra
    estimated_memory = (args.batch_size * memory_per_ray) / (1024 * 1024)

    print(f"💾 Estimated memory per batch: {estimated_memory:.1f} MB")
    print(f"🎯 Total rays to trace: {total_rays:,}")

    try:
        # Setup camera
        aspect_ratio = args.width / args.height
        viewport_height = 2.0
        viewport_width = aspect_ratio * viewport_height
        focal_length = 1.0

        origin = torch.tensor([0, 0, 0], device=device, dtype=torch.float32)
        horizontal = torch.tensor([viewport_width, 0, 0], device=device, dtype=torch.float32)
        vertical = torch.tensor([0, viewport_height, 0], device=device, dtype=torch.float32)
        lower_left_corner = origin - horizontal/2 - vertical/2 - torch.tensor([0, 0, focal_length], device=device)

        # Setup scene
        spheres = setup_scene(device)
        print(f"🏗️ Scene setup: {len(spheres)} objects")

        # Initialize image buffer
        image = torch.zeros(args.height, args.width, 3, device=device, dtype=torch.float32)
        previous_image = torch.zeros_like(image)

        rays_traced = 0
        start_time = time.time()
        timeout_start = time.time()

        print(f"🚀 Starting ray tracing...")
        print(f"🎯 Will stop when quality target {args.quality_target:.1%} is reached or {args.max_runtime}s timeout")

        # Process image in batches of rays
        actual_samples = 0
        convergence_achieved = False
        termination_reason = "max_samples"

        for sample in range(args.samples):
            # Safety timeout check
            if time.time() - timeout_start > args.max_runtime:
                print(f"⏰ Ray tracing timeout after {args.max_runtime}s - stopping early")
                termination_reason = "timeout"
                break

            sample_start = time.time()

            # Store previous image for convergence check
            if sample >= args.min_samples:
                previous_image.copy_(image)

            batch_timeout = False
            for y_start in range(0, args.height, args.batch_size):
                # Check timeout in inner loops too
                if time.time() - timeout_start > args.max_runtime:
                    print(f"⏰ Timeout during batch processing - stopping early")
                    termination_reason = "timeout"
                    batch_timeout = True
                    break

                y_end = min(y_start + args.batch_size, args.height)

                for x_start in range(0, args.width, args.batch_size):
                    # Check timeout more frequently
                    if time.time() - timeout_start > args.max_runtime:
                        termination_reason = "timeout"
                        batch_timeout = True
                        break

                    x_end = min(x_start + args.batch_size, args.width)

                    # Create batch of rays
                    batch_height = y_end - y_start
                    batch_width = x_end - x_start

                    # Generate pixel coordinates with jittering for anti-aliasing
                    y_coords, x_coords = torch.meshgrid(
                        torch.arange(y_start, y_end, device=device, dtype=torch.float32),
                        torch.arange(x_start, x_end, device=device, dtype=torch.float32),
                        indexing='ij'
                    )

                    # Add random jitter for anti-aliasing
                    u = (x_coords + torch.rand_like(x_coords)) / args.width
                    v = (y_coords + torch.rand_like(y_coords)) / args.height

                    # Calculate ray directions
                    ray_direction = (lower_left_corner.unsqueeze(0).unsqueeze(0) +
                                   u.unsqueeze(-1) * horizontal.unsqueeze(0).unsqueeze(0) +
                                   v.unsqueeze(-1) * vertical.unsqueeze(0).unsqueeze(0) -
                                   origin.unsqueeze(0).unsqueeze(0))

                    # Normalize ray directions
                    ray_direction = ray_direction / torch.norm(ray_direction, dim=-1, keepdim=True)

                    # Ray origins (all from camera)
                    ray_origin = origin.unsqueeze(0).unsqueeze(0).expand(batch_height, batch_width, -1)

                    # Trace rays
                    color = trace_ray(ray_origin, ray_direction, spheres, 0, args.max_depth, device)

                    # Accumulate color (average over samples)
                    if sample == 0:
                        image[y_start:y_end, x_start:x_end] = color
                    else:
                        # Running average
                        alpha = 1.0 / (sample + 1)
                        image[y_start:y_end, x_start:x_end] = (1 - alpha) * image[y_start:y_end, x_start:x_end] + alpha * color

                    rays_traced += batch_height * batch_width

                    # Small delay for system stability and more frequent timeout checks
                    if rays_traced % (args.batch_size * 2) == 0:
                        time.sleep(0.001)  # Reduced delay
                        # Additional timeout check
                        if time.time() - timeout_start > args.max_runtime:
                            termination_reason = "timeout"
                            batch_timeout = True
                            break

                if batch_timeout:
                    break

            if batch_timeout:
                break

            actual_samples = sample + 1

            # Quality convergence check after minimum samples
            if sample >= args.min_samples:
                # Calculate image difference (convergence metric)
                diff = torch.abs(image - previous_image)
                mean_diff = torch.mean(diff).item()
                max_diff = torch.max(diff).item()

                # Quality score: lower difference = higher quality
                quality_score = 1.0 - min(mean_diff, 1.0)

                # Check if convergence target is reached
                if quality_score >= args.quality_target:
                    convergence_achieved = True
                    termination_reason = "convergence"
                    print(f"🎯 Quality target {args.quality_target:.1%} achieved! (Current: {quality_score:.1%})")
                    print(f"   Mean pixel change: {mean_diff:.4f}, Max change: {max_diff:.4f}")
                    print(f"   Converged after {actual_samples} samples")
                    break

            # Sample progress
            sample_time = time.time() - sample_start
            elapsed = time.time() - start_time

            # Report progress more frequently, including quality metrics
            if (sample + 1) % max(1, min(2, args.samples // 5)) == 0 or sample >= args.min_samples:
                rays_per_sec = rays_traced / elapsed if elapsed > 0 else 0

                if sample >= args.min_samples:
                    print(f"⚡ Sample {sample + 1}/{args.samples} - "
                          f"{rays_per_sec:,.0f} rays/sec - "
                          f"Quality: {quality_score:.1%} - "
                          f"Time: {sample_time:.2f}s")
                else:
                    print(f"⚡ Sample {sample + 1}/{args.samples} - "
                          f"{rays_per_sec:,.0f} rays/sec - "
                          f"Time: {sample_time:.2f}s (building up...)")

        # Synchronize GPU operations
        if device.type == 'cuda':
            torch.cuda.synchronize()

        total_time = time.time() - start_time

        # Apply gamma correction (simplified)
        image = torch.sqrt(torch.clamp(image, 0, 1))

        # Calculate final statistics based on actual work done
        total_rays_traced = rays_traced  # Use actual rays traced, not theoretical maximum
        rays_per_sec = total_rays_traced / total_time if total_time > 0 else 0
        pixels_per_sec = total_pixels / total_time if total_time > 0 else 0

        # Estimate computational complexity
        estimated_operations_per_ray = args.max_depth * len(spheres) * 10  # Rough estimate
        total_operations = total_rays_traced * estimated_operations_per_ray
        operations_per_sec = total_operations / total_time / 1e9 if total_time > 0 else 0  # GFLOPS

        # Report completion status
        if termination_reason == "convergence":
            print(f"\n🎉 Ray tracing completed via quality convergence!")
            print(f"🎯 Achieved {args.quality_target:.1%} quality target in {actual_samples} samples")
        elif termination_reason == "timeout":
            print(f"\n⏰ Ray tracing completed via timeout!")
            print(f"🕒 Stopped after {args.max_runtime}s with {actual_samples} samples")
        else:
            print(f"\n🎉 Ray tracing completed after maximum samples!")
            print(f"📊 Completed all {actual_samples} samples")

        print(f"⏱️ Total time: {total_time:.2f} seconds")
        print(f"📊 Performance:")
        print(f"   Rays traced: {total_rays_traced:,}")
        print(f"   Rays/second: {rays_per_sec:,.0f}")
        print(f"   Pixels/second: {pixels_per_sec:,.0f}")
        print(f"   Estimated GFLOPS: {operations_per_sec:.2f}")
        print(f"\n🎨 Rendering details:")
        print(f"   Resolution: {args.width}x{args.height}")
        print(f"   Actual samples per pixel: {actual_samples}")
        print(f"   Max possible samples: {args.samples}")
        print(f"   Max bounce depth: {args.max_depth}")
        print(f"   Scene complexity: {len(spheres)} objects")
        print(f"   Termination reason: {termination_reason}")

        # Memory cleanup
        if device.type == 'cuda':
            memory_allocated = torch.cuda.memory_allocated() / 1024**2
            peak_memory = torch.cuda.max_memory_allocated() / 1024**2
            print(f"💾 GPU Memory - Current: {memory_allocated:.1f} MB, Peak: {peak_memory:.1f} MB")
            torch.cuda.empty_cache()
        elif device.type == 'mps':
            print("🍎 MPS ray tracing completed")

    except torch.cuda.OutOfMemoryError:
        print("❌ GPU out of memory! Try reducing --batch-size, --width, --height, or --samples")
        return 1
    except Exception as e:
        print(f"❌ Error during ray tracing: {e}")
        return 1

    print(f"✨ Ray tracing benchmark completed successfully!")
    print(f"🌟 Rendered {args.width}x{args.height} image with task-based termination")
    return 0

if __name__ == "__main__":
    try:
        exit(main())
    except KeyboardInterrupt:
        print("\n⏹️  Ray tracing interrupted by user")
        exit(0)
    except Exception as e:
        print(f"\n❌ Ray tracing failed: {e}")
        exit(1)