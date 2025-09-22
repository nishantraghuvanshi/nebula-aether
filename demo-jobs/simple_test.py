#!/usr/bin/env python3
"""
Simple CPU-intensive test that should show up in Activity Monitor
Uses only standard Python libraries - no external dependencies
"""

import time
import argparse
import os
import math
import random

def cpu_intensive_work(duration=10, intensity=1000000):
    """Perform CPU-intensive work for specified duration"""
    print(f"Starting CPU-intensive work for {duration} seconds...")
    print(f"Process PID: {os.getpid()}")

    start_time = time.time()
    iteration = 0

    while time.time() - start_time < duration:
        # CPU-intensive mathematical operations
        for i in range(intensity):
            # Mix of operations to keep CPU busy
            result = math.sqrt(i) * math.sin(i) + math.cos(i)
            result = result ** 2
            result = math.log(abs(result) + 1)

        iteration += 1
        elapsed = time.time() - start_time
        print(f"Iteration {iteration} - Elapsed: {elapsed:.1f}s - PID: {os.getpid()}")

        # Brief pause to allow monitoring
        time.sleep(0.1)

    print(f"Completed! Total iterations: {iteration}")
    print(f"Process PID {os.getpid()} finished")

def main():
    parser = argparse.ArgumentParser(description='Simple CPU test')
    parser.add_argument('--duration', type=int, default=10,
                      help='Duration in seconds (default: 10)')
    parser.add_argument('--intensity', type=int, default=1000000,
                      help='Intensity factor (default: 1000000)')
    parser.add_argument('--device', type=str, default='cpu',
                      help='Device type (ignored for CPU test)')

    args = parser.parse_args()

    print("=" * 50)
    print("SIMPLE CPU TEST STARTING")
    print(f"Duration: {args.duration} seconds")
    print(f"Intensity: {args.intensity}")
    print(f"PID: {os.getpid()}")
    print("=" * 50)

    cpu_intensive_work(args.duration, args.intensity)

    print("=" * 50)
    print("TEST COMPLETED")
    print("=" * 50)

if __name__ == "__main__":
    main()