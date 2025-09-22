#!/usr/bin/env python3
"""
Image Inference Simulation - GPU/CPU Stress Test
Simulates batch image classification without external dependencies
Mac-compatible version with automatic MPS/CPU detection
"""

import torch
import torch.nn as nn
import time
import argparse
import sys
import random
import math

class SimpleResNet(nn.Module):
    """Simplified ResNet-like model for inference simulation"""

    def __init__(self, num_classes=1000):
        super(SimpleResNet, self).__init__()

        # Simulated convolutional layers (using Linear for simplicity)
        self.conv_block1 = nn.Sequential(
            nn.Linear(224*224*3, 4096),  # Simulate conv layer
            nn.ReLU(),
            nn.Dropout(0.1)
        )

        self.conv_block2 = nn.Sequential(
            nn.Linear(4096, 2048),
            nn.ReLU(),
            nn.Dropout(0.1)
        )

        self.conv_block3 = nn.Sequential(
            nn.Linear(2048, 1024),
            nn.ReLU(),
            nn.Dropout(0.1)
        )

        self.conv_block4 = nn.Sequential(
            nn.Linear(1024, 512),
            nn.ReLU(),
            nn.Dropout(0.1)
        )

        # Final classification layer
        self.classifier = nn.Linear(512, num_classes)

    def forward(self, x):
        x = x.view(x.size(0), -1)  # Flatten
        x = self.conv_block1(x)
        x = self.conv_block2(x)
        x = self.conv_block3(x)
        x = self.conv_block4(x)
        x = self.classifier(x)
        return x

def generate_image_batch(batch_size, device):
    """Generate synthetic image data (224x224x3)"""
    # Simulate RGB images
    images = torch.randn(batch_size, 224*224*3, device=device)
    return images

def main():
    parser = argparse.ArgumentParser(description='Image Inference Simulation')
    parser.add_argument('--batch-size', type=int, default=32, help='Batch size')
    parser.add_argument('--num-batches', type=int, default=50, help='Number of batches to process')
    parser.add_argument('--device', type=str, default='auto', help='Device to use')
    parser.add_argument('--model-size', type=str, default='medium',
                       choices=['small', 'medium', 'large'], help='Model size')
    args = parser.parse_args()

    print(f"🔍 Starting Image Inference Simulation")
    print(f"   Batch Size: {args.batch_size}, Batches: {args.num_batches}")
    print(f"   Model Size: {args.model_size}")

    # Device selection with better Mac support
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

    # Adjust model size based on parameter
    if args.model_size == 'small':
        num_classes = 100
    elif args.model_size == 'medium':
        num_classes = 1000  # ImageNet-like
    else:  # large
        num_classes = 10000

    # Initialize model
    print("🏗️ Initializing inference model...")
    model = SimpleResNet(num_classes).to(device)
    model.eval()  # Set to evaluation mode

    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    print(f"🔢 Model has {total_params:,} parameters")

    # Warm up the model
    print("🔥 Warming up model...")
    with torch.no_grad():
        warmup_data = generate_image_batch(args.batch_size, device)
        _ = model(warmup_data)

    # Inference loop
    print("🔍 Starting batch inference...")
    start_time = time.time()

    total_images = 0
    inference_times = []

    with torch.no_grad():
        for batch_idx in range(args.num_batches):
            batch_start = time.time()

            # Generate synthetic image batch
            images = generate_image_batch(args.batch_size, device)

            # Run inference
            outputs = model(images)

            # Simulate post-processing
            predictions = torch.softmax(outputs, dim=1)
            top_predictions = torch.topk(predictions, k=5, dim=1)

            batch_time = time.time() - batch_start
            inference_times.append(batch_time)
            total_images += args.batch_size

            # Progress indicator every 10 batches
            if batch_idx % 10 == 0 or batch_idx == args.num_batches - 1:
                images_per_sec = args.batch_size / batch_time
                print(f"⚡ Batch {batch_idx+1}/{args.num_batches} - "
                      f"{images_per_sec:.1f} images/sec - "
                      f"Time: {batch_time:.3f}s")

            # Small delay to simulate realistic processing
            time.sleep(0.02)

    total_time = time.time() - start_time
    avg_batch_time = sum(inference_times) / len(inference_times)
    total_throughput = total_images / total_time

    print(f"\n📊 Inference Results:")
    print(f"   Total Images Processed: {total_images:,}")
    print(f"   Total Time: {total_time:.2f} seconds")
    print(f"   Average Batch Time: {avg_batch_time:.3f} seconds")
    print(f"   Overall Throughput: {total_throughput:.1f} images/second")
    print(f"   Per-Image Time: {(total_time/total_images)*1000:.2f} ms")

    # Memory cleanup
    if device.type == 'cuda':
        print(f"🧹 GPU Memory: {torch.cuda.memory_allocated()/1024**3:.2f}GB allocated")
        torch.cuda.empty_cache()
    elif device.type == 'mps':
        print(f"🍎 MPS device used for inference")

    print("✨ Image Inference Simulation completed successfully!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️  Inference interrupted by user")
    except Exception as e:
        print(f"❌ Inference failed: {e}")
        sys.exit(1)