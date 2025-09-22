#!/usr/bin/env python3
"""
Neural Network Training Job - GPU/CPU Stress Test
Trains a neural network on synthetic data to generate realistic compute load
Mac-compatible version with automatic MPS/CPU detection
"""

import torch
import torch.nn as nn
import torch.optim as optim
import time
import argparse
import sys
import os
import random
import math

class TrainingNet(nn.Module):
    def __init__(self, input_size=768, hidden_sizes=[1536, 768, 384, 192], num_classes=10):
        super(TrainingNet, self).__init__()
        # Deliberately large network to stress GPU/CPU
        layers = []
        prev_size = input_size

        for hidden_size in hidden_sizes:
            layers.extend([
                nn.Linear(prev_size, hidden_size),
                nn.ReLU(),
                nn.Dropout(0.2)
            ])
            prev_size = hidden_size

        layers.append(nn.Linear(prev_size, num_classes))
        self.network = nn.Sequential(*layers)

    def forward(self, x):
        return self.network(x)

def generate_synthetic_data(batch_size, input_size, num_classes, device):
    """Generate synthetic training data"""
    # Create random input data
    X = torch.randn(batch_size, input_size, device=device)
    # Create random labels
    y = torch.randint(0, num_classes, (batch_size,), device=device)
    return X, y

def main():
    parser = argparse.ArgumentParser(description='Neural Network Training Job')
    parser.add_argument('--epochs', type=int, default=10, help='Number of epochs')
    parser.add_argument('--batch-size', type=int, default=384, help='Batch size')
    parser.add_argument('--device', type=str, default='auto', help='Device to use')
    parser.add_argument('--input-size', type=int, default=768, help='Input feature size')
    parser.add_argument('--batches-per-epoch', type=int, default=75, help='Batches per epoch')
    args = parser.parse_args()

    print(f"🚀 Starting Neural Network Training Job")
    print(f"   Epochs: {args.epochs}, Batch Size: {args.batch_size}")
    print(f"   Input Size: {args.input_size}, Batches/Epoch: {args.batches_per_epoch}")

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

    # Model parameters - reduced by 25% for stability
    input_size = args.input_size
    num_classes = 10
    hidden_sizes = [1536, 768, 384, 192]  # Reduced network size for system stability

    print("📊 Using synthetic training data for stress testing...")

    # Initialize model
    print("🏗️ Initializing neural network...")
    model = TrainingNet(input_size, hidden_sizes, num_classes).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    print(f"🔢 Model has {total_params:,} parameters")

    # Training loop
    print("🏋️ Starting training...")
    start_time = time.time()

    for epoch in range(args.epochs):
        epoch_start = time.time()
        running_loss = 0.0
        model.train()

        for batch_idx in range(args.batches_per_epoch):
            # Generate synthetic batch
            data, target = generate_synthetic_data(args.batch_size, input_size, num_classes, device)

            optimizer.zero_grad()
            output = model(data)
            loss = criterion(output, target)
            loss.backward()
            optimizer.step()

            running_loss += loss.item()

            # Progress indicator every 20 batches
            if batch_idx % 20 == 0:
                print(f"⚡ Epoch {epoch+1}/{args.epochs}, Batch {batch_idx+1}/{args.batches_per_epoch}, Loss: {loss.item():.4f}")

            # Small delay to simulate real training
            time.sleep(0.05)

        epoch_time = time.time() - epoch_start
        avg_loss = running_loss / args.batches_per_epoch
        print(f"✅ Epoch {epoch+1} completed in {epoch_time:.2f}s, Average Loss: {avg_loss:.4f}")

    total_time = time.time() - start_time
    print(f"🎉 Training completed in {total_time:.2f} seconds")

    # Final model evaluation
    model.eval()
    with torch.no_grad():
        test_data, test_target = generate_synthetic_data(args.batch_size, input_size, num_classes, device)
        test_output = model(test_data)
        test_loss = criterion(test_output, test_target)
        pred = test_output.argmax(dim=1, keepdim=True)
        correct = pred.eq(test_target.view_as(pred)).sum().item()
        accuracy = 100. * correct / args.batch_size
        print(f"📊 Final Test Accuracy: {accuracy:.1f}%")

    # Memory cleanup
    if device.type == 'cuda':
        print(f"🧹 GPU Memory: {torch.cuda.memory_allocated()/1024**3:.2f}GB allocated")
        torch.cuda.empty_cache()
    elif device.type == 'mps':
        print(f"🍎 MPS device used for training")

    print("✨ Neural Network Training Job completed successfully!")
    print(f"⏱️  Total compute time: {total_time:.1f} seconds")
    print(f"🔥 Average time per epoch: {total_time/args.epochs:.1f} seconds")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️  Training interrupted by user")
    except Exception as e:
        print(f"❌ Training failed: {e}")
        sys.exit(1)