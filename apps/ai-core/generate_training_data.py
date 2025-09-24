#!/usr/bin/env python3
"""
Enhanced Training Data Generator for GPU Scheduling AI Model

Generates realistic training data based on actual GPU workload patterns and scenarios.
This replaces the simple LLM-generated synthetic data with domain-specific realistic scenarios.
"""

import random
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import json

class GpuWorkloadScenario:
    """Defines realistic GPU workload scenarios"""

    def __init__(self, name: str, job_type: str, characteristics: Dict):
        self.name = name
        self.job_type = job_type
        self.characteristics = characteristics

# Define realistic GPU workload scenarios
WORKLOAD_SCENARIOS = [
    # Training scenarios
    GpuWorkloadScenario("Large Language Model Training", "training", {
        "memory_usage": (18000, 23000),     # High memory usage
        "utilization": (85, 98),            # High utilization
        "temperature": (70, 82),            # High heat generation
        "power": (220, 280),                # High power draw
        "duration": (1800, 7200),           # 30 minutes to 2 hours
        "optimal_conditions": {
            "max_temp": 78,
            "max_mem_util": 90,
            "max_power": 260
        }
    }),

    GpuWorkloadScenario("Computer Vision Training", "training", {
        "memory_usage": (12000, 20000),
        "utilization": (75, 95),
        "temperature": (65, 78),
        "power": (180, 240),
        "duration": (900, 3600),
        "optimal_conditions": {
            "max_temp": 75,
            "max_mem_util": 85,
            "max_power": 220
        }
    }),

    GpuWorkloadScenario("Small Model Training", "training", {
        "memory_usage": (4000, 12000),
        "utilization": (60, 85),
        "temperature": (55, 70),
        "power": (150, 200),
        "duration": (300, 1800),
        "optimal_conditions": {
            "max_temp": 70,
            "max_mem_util": 80,
            "max_power": 180
        }
    }),

    # Inference scenarios
    GpuWorkloadScenario("Real-time Inference", "inference", {
        "memory_usage": (2000, 8000),
        "utilization": (30, 70),
        "temperature": (45, 65),
        "power": (120, 180),
        "duration": (60, 300),
        "optimal_conditions": {
            "max_temp": 65,
            "max_mem_util": 60,
            "max_power": 160
        }
    }),

    GpuWorkloadScenario("Batch Inference", "inference", {
        "memory_usage": (8000, 16000),
        "utilization": (50, 80),
        "temperature": (60, 75),
        "power": (160, 220),
        "duration": (180, 900),
        "optimal_conditions": {
            "max_temp": 70,
            "max_mem_util": 75,
            "max_power": 200
        }
    }),

    # Compute scenarios
    GpuWorkloadScenario("Matrix Operations", "compute", {
        "memory_usage": (6000, 14000),
        "utilization": (80, 95),
        "temperature": (70, 80),
        "power": (200, 250),
        "duration": (120, 600),
        "optimal_conditions": {
            "max_temp": 75,
            "max_mem_util": 70,
            "max_power": 230
        }
    }),

    GpuWorkloadScenario("Scientific Computing", "compute", {
        "memory_usage": (10000, 20000),
        "utilization": (70, 90),
        "temperature": (65, 78),
        "power": (180, 240),
        "duration": (600, 3600),
        "optimal_conditions": {
            "max_temp": 72,
            "max_mem_util": 85,
            "max_power": 220
        }
    }),

    # Memory-intensive scenarios
    GpuWorkloadScenario("Large Dataset Processing", "memory", {
        "memory_usage": (20000, 24000),
        "utilization": (40, 70),
        "temperature": (50, 70),
        "power": (140, 200),
        "duration": (300, 1800),
        "optimal_conditions": {
            "max_temp": 65,
            "max_mem_util": 95,
            "max_power": 180
        }
    }),
]

class EnhancedTrainingDataGenerator:
    """Generates realistic training data for GPU scheduling"""

    def __init__(self, total_memory_mb: int = 24576):
        self.total_memory_mb = total_memory_mb
        self.scenarios = WORKLOAD_SCENARIOS

    def generate_gpu_state(self, base_load: float = 0.0) -> Dict:
        """Generate a realistic GPU state"""

        # Base GPU characteristics (idle/low load state)
        base_temp = random.randint(35, 50)
        base_util = max(0, int(base_load * 100) + random.randint(-5, 10))
        base_memory = random.randint(1000, 3000)  # OS and background processes
        base_power = random.randint(80, 120)

        # Clock speeds (vary based on utilization)
        gpu_clock_base = 1200
        mem_clock_base = 5000

        # Performance state based on utilization
        if base_util < 20:
            perf_state = random.choice(["P5", "P8"])
            clock_multiplier = random.uniform(0.6, 0.8)
        elif base_util < 50:
            perf_state = random.choice(["P2", "P3"])
            clock_multiplier = random.uniform(0.8, 0.95)
        else:
            perf_state = random.choice(["P0", "P1"])
            clock_multiplier = random.uniform(0.95, 1.2)

        gpu_clock = int(gpu_clock_base * clock_multiplier)
        mem_clock = int(mem_clock_base * clock_multiplier)

        # Memory controller utilization (correlated with GPU util)
        mem_controller_util = max(0, min(100, base_util + random.randint(-10, 15)))

        # Throttling (rare, but increases with temperature and power)
        throttling_prob = max(0, (base_temp - 75) / 20.0 + (base_power - 200) / 100.0)
        is_throttling = random.random() < throttling_prob
        throttling_reasons = "thermal,power" if is_throttling else ""

        return {
            'gpu_name': random.choice([
                'NVIDIA RTX 4090', 'NVIDIA RTX 4080', 'NVIDIA RTX 4070',
                'NVIDIA RTX 3090', 'NVIDIA A100', 'NVIDIA H100'
            ]),
            'utilization_gpu': base_util,
            'gpu_temp': base_temp,
            'power_draw_w': base_power,
            'gpu_mem_used': base_memory,
            'gpu_mem_total': self.total_memory_mb,
            'utilization_memory_controller': mem_controller_util,
            'clock_gpu_mhz': gpu_clock,
            'clock_mem_mhz': mem_clock,
            'perf_state_numeric': int(perf_state[1:]),
            'is_throttling': 1 if is_throttling else 0,
            'throttling_reasons': throttling_reasons
        }

    def calculate_derived_features(self, gpu_state: Dict, job_requirements: Dict) -> Dict:
        """Calculate derived features for training"""

        memory_utilization_pct = (gpu_state['gpu_mem_used'] / gpu_state['gpu_mem_total']) * 100
        thermal_headroom = max(0, 83 - gpu_state['gpu_temp'])
        power_per_util = gpu_state['power_draw_w'] / max(gpu_state['utilization_gpu'], 1)
        gpu_clock_ratio = gpu_state['clock_gpu_mhz'] / 2000.0
        mem_clock_ratio = gpu_state['clock_mem_mhz'] / 6000.0

        # Job compatibility features
        available_memory = gpu_state['gpu_mem_total'] - gpu_state['gpu_mem_used']
        memory_sufficient = 1 if available_memory >= job_requirements['min_memory_mb'] else 0
        expected_util_match = 1 - abs(gpu_state['utilization_gpu'] - job_requirements['expected_gpu_util']) / 100.0

        priority_weights = {'low': 0.5, 'normal': 1.0, 'high': 1.5}
        priority_weight = priority_weights.get(job_requirements['priority'], 1.0)

        return {
            'memory_utilization_pct': memory_utilization_pct,
            'thermal_headroom': thermal_headroom,
            'power_per_util': power_per_util,
            'gpu_clock_ratio': gpu_clock_ratio,
            'mem_clock_ratio': mem_clock_ratio,
            'memory_sufficient': memory_sufficient,
            'expected_util_match': expected_util_match,
            'priority_weight': priority_weight
        }

    def evaluate_placement_quality(self, gpu_state: Dict, scenario: GpuWorkloadScenario, job_req: Dict) -> float:
        """Evaluate how good this GPU placement would be (0-100 score)"""

        score = 100.0
        optimal = scenario.characteristics['optimal_conditions']

        # Temperature penalty
        if gpu_state['gpu_temp'] > optimal['max_temp']:
            temp_penalty = (gpu_state['gpu_temp'] - optimal['max_temp']) * 3
            score -= temp_penalty

        # Memory availability penalty
        available_memory = gpu_state['gpu_mem_total'] - gpu_state['gpu_mem_used']
        if available_memory < job_req['min_memory_mb']:
            score *= 0.1  # Heavy penalty for insufficient memory
        elif (gpu_state['gpu_mem_used'] / gpu_state['gpu_mem_total']) * 100 > optimal['max_mem_util']:
            mem_penalty = ((gpu_state['gpu_mem_used'] / gpu_state['gpu_mem_total']) * 100 - optimal['max_mem_util']) * 2
            score -= mem_penalty

        # Power penalty
        if gpu_state['power_draw_w'] > optimal['max_power']:
            power_penalty = (gpu_state['power_draw_w'] - optimal['max_power']) * 0.5
            score -= power_penalty

        # Utilization match bonus/penalty
        util_diff = abs(gpu_state['utilization_gpu'] - job_req['expected_gpu_util'])
        if util_diff > 30:
            score -= util_diff * 0.5
        elif util_diff < 10:
            score += 5  # Bonus for good match

        # Throttling penalty
        if gpu_state['is_throttling']:
            score *= 0.6

        # Performance state bonus
        if gpu_state['perf_state_numeric'] <= 2:
            score += 5  # Bonus for high performance state

        return max(0, min(100, score))

    def generate_job_requirements(self, scenario: GpuWorkloadScenario) -> Dict:
        """Generate job requirements for a scenario"""

        chars = scenario.characteristics

        return {
            'min_memory_mb': random.randint(*chars['memory_usage']),
            'expected_gpu_util': random.randint(*chars['utilization']),
            'max_duration_sec': random.randint(*chars['duration']),
            'priority': random.choice(['low', 'normal', 'normal', 'high']),  # Normal is more common
            'compute_intensity': scenario.job_type
        }

    def generate_training_sample(self) -> Dict:
        """Generate a single training sample"""

        # Choose a random scenario
        scenario = random.choice(self.scenarios)

        # Generate job requirements for this scenario
        job_req = self.generate_job_requirements(scenario)

        # Generate GPU state (with some existing load)
        existing_load = random.uniform(0.0, 0.7)  # 0-70% existing load
        gpu_state = self.generate_gpu_state(existing_load)

        # For training variety, sometimes generate suboptimal conditions
        if random.random() < 0.3:  # 30% chance of suboptimal conditions
            # Add some stress to make it less optimal
            gpu_state['gpu_temp'] += random.randint(10, 20)
            gpu_state['power_draw_w'] += random.randint(20, 50)
            gpu_state['utilization_gpu'] = min(100, gpu_state['utilization_gpu'] + random.randint(20, 40))

        # Calculate derived features
        derived = self.calculate_derived_features(gpu_state, job_req)

        # Calculate performance score
        performance_score = self.evaluate_placement_quality(gpu_state, scenario, job_req)

        # Calculate risk factors
        thermal_risk = max(0, min(1, (gpu_state['gpu_temp'] - 75) / 15.0))
        memory_risk = max(0, min(1, (derived['memory_utilization_pct'] - 80) / 20.0))

        # Combine all features
        sample = {
            # Core telemetry
            'utilization_gpu': gpu_state['utilization_gpu'],
            'gpu_temp': gpu_state['gpu_temp'],
            'power_draw_w': gpu_state['power_draw_w'],
            'gpu_mem_used': gpu_state['gpu_mem_used'],
            'gpu_mem_total': gpu_state['gpu_mem_total'],
            'utilization_memory_controller': gpu_state['utilization_memory_controller'],
            'clock_gpu_mhz': gpu_state['clock_gpu_mhz'],
            'clock_mem_mhz': gpu_state['clock_mem_mhz'],

            # Job type encoding
            'job_type_training': 1 if scenario.job_type == 'training' else 0,
            'job_type_inference': 1 if scenario.job_type == 'inference' else 0,
            'job_type_compute': 1 if scenario.job_type == 'compute' else 0,
            'job_type_memory': 1 if scenario.job_type == 'memory' else 0,

            # Derived features
            'memory_utilization_pct': derived['memory_utilization_pct'],
            'thermal_headroom': derived['thermal_headroom'],
            'power_per_util': derived['power_per_util'],
            'gpu_clock_ratio': derived['gpu_clock_ratio'],
            'mem_clock_ratio': derived['mem_clock_ratio'],
            'perf_state_numeric': gpu_state['perf_state_numeric'],
            'is_throttling': gpu_state['is_throttling'],
            'memory_sufficient': derived['memory_sufficient'],
            'expected_util_match': derived['expected_util_match'],
            'priority_weight': derived['priority_weight'],

            # Target variables
            'performance_score': performance_score,
            'thermal_risk': thermal_risk,
            'memory_risk': memory_risk,

            # Metadata (not used in training)
            'scenario_name': scenario.name,
            'job_type': scenario.job_type
        }

        return sample

    def generate_dataset(self, num_samples: int = 5000) -> pd.DataFrame:
        """Generate a complete training dataset"""

        print(f"Generating {num_samples} realistic training samples...")

        samples = []
        for i in range(num_samples):
            if i % 500 == 0:
                print(f"  Generated {i}/{num_samples} samples...")

            sample = self.generate_training_sample()
            samples.append(sample)

        df = pd.DataFrame(samples)

        # Print dataset statistics
        print(f"\nDataset Statistics:")
        print(f"  Total samples: {len(df)}")
        print(f"  Job type distribution:")
        for job_type in ['training', 'inference', 'compute', 'memory']:
            count = df[f'job_type_{job_type}'].sum()
            print(f"    {job_type}: {count} ({count/len(df)*100:.1f}%)")

        print(f"  Performance score distribution:")
        print(f"    Mean: {df['performance_score'].mean():.1f}")
        print(f"    Std: {df['performance_score'].std():.1f}")
        print(f"    Min: {df['performance_score'].min():.1f}")
        print(f"    Max: {df['performance_score'].max():.1f}")

        return df

def main():
    """Generate and save enhanced training data"""

    generator = EnhancedTrainingDataGenerator()

    # Generate training dataset
    df = generator.generate_dataset(5000)

    # Save to CSV
    output_file = 'enhanced_training_data.csv'
    df.to_csv(output_file, index=False)
    print(f"\nSaved enhanced training data to {output_file}")

    # Save metadata
    metadata = {
        'total_samples': len(df),
        'features': list(df.columns),
        'scenarios': [s.name for s in WORKLOAD_SCENARIOS],
        'feature_count': len(df.columns),
        'job_types': ['training', 'inference', 'compute', 'memory']
    }

    with open('training_data_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"Saved metadata to training_data_metadata.json")
    print(f"\nEnhanced training data generation complete!")

if __name__ == "__main__":
    main()