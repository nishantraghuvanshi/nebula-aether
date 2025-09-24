# aether/apps/ai-core/simulator.py
# Enhanced synthetic training data generation for multi-vendor GPU scheduling

import pandas as pd
import numpy as np
import random

def generate_training_data(num_samples=5000):
    """
    Generates comprehensive and realistic synthetic dataset for GPU job placement.
    
    This function creates training data that matches the enhanced feature set used by
    the AI Core, including vendor-specific characteristics, memory constraints, and
    realistic GPU behavior patterns.
    """
    
    print(f"Generating {num_samples} training samples with enhanced features...")
    
    # Initialize data structure
    data = {
        # Core GPU metrics
        'gpu_temp': [],
        'gpu_mem_used': [],
        'gpu_mem_total': [],
        'utilization_gpu': [],
        'power_draw_w': [],
        
        # Derived features
        'mem_available_after_job': [],
        'mem_utilization_percent': [],
        'temp_efficiency': [],
        'power_efficiency': [],
        
        # Job context
        'vram_required_mb': [],
        'job_type_training': [],
        'priority': [],
        
        # GPU characteristics
        'is_throttling': [],
        'vendor_nvidia': [],
        'vendor_amd': [],
        'vendor_intel': [],
        'vendor_apple': [],
        
        # Target variable
        'good_placement': []
    }
    
    # Define GPU vendor characteristics
    gpu_vendors = [
        {
            'name': 'nvidia',
            'weight': 0.6,  # 60% of samples
            'temp_range': (40, 85),
            'power_range': (150, 400),
            'memory_options': [8192, 12288, 16384, 24576, 32768, 49152],  # Common NVIDIA memory sizes
            'base_efficiency': 1.0
        },
        {
            'name': 'amd',
            'weight': 0.2,  # 20% of samples
            'temp_range': (45, 90),
            'power_range': (180, 350),
            'memory_options': [8192, 16384, 24576, 32768],  # Common AMD memory sizes
            'base_efficiency': 0.95
        },
        {
            'name': 'intel',
            'weight': 0.1,  # 10% of samples
            'temp_range': (50, 80),
            'power_range': (75, 200),
            'memory_options': [4096, 8192, 12288],  # Integrated/discrete Intel
            'base_efficiency': 0.85
        },
        {
            'name': 'apple',
            'weight': 0.1,  # 10% of samples
            'temp_range': (35, 70),
            'power_range': (20, 80),
            'memory_options': [8192, 16384, 32768, 65536, 131072],  # Unified memory
            'base_efficiency': 1.1
        }
    ]
    
    # Job types and their characteristics
    job_types = [
        {'name': 'training', 'weight': 0.7, 'vram_multiplier': 1.5, 'temp_sensitivity': 1.2},
        {'name': 'inference', 'weight': 0.3, 'vram_multiplier': 0.8, 'temp_sensitivity': 0.9}
    ]
    
    for i in range(num_samples):
        # Select GPU vendor based on weights
        vendor_choice = np.random.choice(
            [v['name'] for v in gpu_vendors],
            p=[v['weight'] for v in gpu_vendors]
        )
        vendor_config = next(v for v in gpu_vendors if v['name'] == vendor_choice)
        
        # Select job type
        job_choice = np.random.choice(
            [j['name'] for j in job_types],
            p=[j['weight'] for j in job_types]
        )
        job_config = next(j for j in job_types if j['name'] == job_choice)
        
        # Generate base GPU metrics
        base_utilization = np.random.randint(0, 101)
        
        # Temperature correlated with utilization and vendor characteristics
        temp_min, temp_max = vendor_config['temp_range']
        gpu_temp = int(temp_min + (base_utilization / 100) * (temp_max - temp_min) + 
                      np.random.normal(0, 5))
        gpu_temp = max(temp_min, min(temp_max + 10, gpu_temp))  # Allow some overflow
        
        # Power draw correlated with utilization, temperature, and vendor
        power_min, power_max = vendor_config['power_range']
        power_base = power_min + (base_utilization / 100) * (power_max - power_min)
        power_temp_factor = 1 + (gpu_temp - temp_min) / (temp_max - temp_min) * 0.2
        power_draw_w = int(power_base * power_temp_factor * np.random.uniform(0.8, 1.2))
        
        # Memory configuration
        gpu_mem_total = random.choice(vendor_config['memory_options'])
        mem_usage_percent = np.random.beta(2, 5) * 100  # Skewed towards lower usage
        gpu_mem_used = int((mem_usage_percent / 100) * gpu_mem_total)
        
        # Job VRAM requirement
        base_vram_req = np.random.choice([1024, 2048, 4096, 6144, 8192, 12288, 16384])
        vram_required_mb = int(base_vram_req * job_config['vram_multiplier'] * np.random.uniform(0.7, 1.3))
        
        # Job priority (0-10) - using normalized probabilities
        priority_probs = np.array([0.3, 0.2, 0.15, 0.1, 0.08, 0.07, 0.05, 0.03, 0.015, 0.01, 0.005])
        priority_probs = priority_probs / priority_probs.sum()  # Normalize to sum to 1.0
        priority = np.random.choice(range(11), p=priority_probs)
        
        # Calculate derived features
        mem_available_after_job = (gpu_mem_total - gpu_mem_used) - vram_required_mb
        mem_utilization_percent = (gpu_mem_used / gpu_mem_total) * 100 if gpu_mem_total > 0 else 0
        temp_efficiency = max(0, 100 - gpu_temp) / 100
        power_efficiency = base_utilization / max(power_draw_w, 1)
        
        # Throttling simulation (more sophisticated)
        is_throttling = 0
        if gpu_temp > 85 and power_draw_w > (power_max * 0.8):
            is_throttling = 1
        elif gpu_temp > 90:
            is_throttling = 1
        elif vendor_choice == 'intel' and gpu_temp > 75:  # Intel runs hotter
            is_throttling = 1
        
        # Vendor one-hot encoding
        vendor_nvidia = 1 if vendor_choice == 'nvidia' else 0
        vendor_amd = 1 if vendor_choice == 'amd' else 0
        vendor_intel = 1 if vendor_choice == 'intel' else 0
        vendor_apple = 1 if vendor_choice == 'apple' else 0
        
        # Job type encoding
        job_type_training = 1 if job_choice == 'training' else 0
        
        # Determine good placement (sophisticated logic)
        good_placement = 1  # Start optimistic
        
        # Hard constraints (immediate rejection)
        if mem_available_after_job < 0:
            good_placement = 0  # Not enough memory
        elif is_throttling:
            good_placement = 0  # Never place on throttling GPU
        elif gpu_temp > 95:
            good_placement = 0  # Critically hot
        
        # Soft constraints (probabilistic rejection)
        elif job_type_training and gpu_temp > 80:
            good_placement = 0 if np.random.random() < 0.8 else 1  # Training sensitive to heat
        elif mem_available_after_job < vram_required_mb * 0.5:
            good_placement = 0 if np.random.random() < 0.7 else 1  # Tight memory
        elif base_utilization > 90:
            good_placement = 0 if np.random.random() < 0.6 else 1  # Very busy GPU
        elif vendor_choice == 'apple' and job_type_training and vram_required_mb > 16384:
            good_placement = 0 if np.random.random() < 0.9 else 1  # Apple Silicon memory limits
        
        # Vendor-specific preferences
        elif vendor_choice == 'nvidia' and job_type_training:
            good_placement = 1 if np.random.random() < 0.9 else good_placement  # NVIDIA good for training
        elif vendor_choice == 'apple' and not job_type_training:
            good_placement = 1 if np.random.random() < 0.85 else good_placement  # Apple good for inference
        
        # Store all features
        data['gpu_temp'].append(gpu_temp)
        data['gpu_mem_used'].append(gpu_mem_used)
        data['gpu_mem_total'].append(gpu_mem_total)
        data['utilization_gpu'].append(base_utilization)
        data['power_draw_w'].append(power_draw_w)
        
        data['mem_available_after_job'].append(mem_available_after_job)
        data['mem_utilization_percent'].append(mem_utilization_percent)
        data['temp_efficiency'].append(temp_efficiency)
        data['power_efficiency'].append(power_efficiency)
        
        data['vram_required_mb'].append(vram_required_mb)
        data['job_type_training'].append(job_type_training)
        data['priority'].append(priority)
        
        data['is_throttling'].append(is_throttling)
        data['vendor_nvidia'].append(vendor_nvidia)
        data['vendor_amd'].append(vendor_amd)
        data['vendor_intel'].append(vendor_intel)
        data['vendor_apple'].append(vendor_apple)
        
        data['good_placement'].append(good_placement)
    
    # Create DataFrame and save
    df = pd.DataFrame(data)
    
    # Print statistics
    print(f"\nDataset Statistics:")
    print(f"Total samples: {len(df)}")
    print(f"Good placements: {df['good_placement'].sum()} ({df['good_placement'].mean()*100:.1f}%)")
    print(f"Bad placements: {len(df) - df['good_placement'].sum()} ({(1-df['good_placement'].mean())*100:.1f}%)")
    print(f"\nVendor distribution:")
    print(f"  NVIDIA: {df['vendor_nvidia'].sum()} ({df['vendor_nvidia'].mean()*100:.1f}%)")
    print(f"  AMD: {df['vendor_amd'].sum()} ({df['vendor_amd'].mean()*100:.1f}%)")
    print(f"  Intel: {df['vendor_intel'].sum()} ({df['vendor_intel'].mean()*100:.1f}%)")
    print(f"  Apple: {df['vendor_apple'].sum()} ({df['vendor_apple'].mean()*100:.1f}%)")
    print(f"\nJob type distribution:")
    print(f"  Training: {df['job_type_training'].sum()} ({df['job_type_training'].mean()*100:.1f}%)")
    print(f"  Inference: {len(df) - df['job_type_training'].sum()} ({(1-df['job_type_training'].mean())*100:.1f}%)")
    
    # Save to CSV
    df.to_csv('training_data.csv', index=False)
    print(f"\nSaved enhanced training data to training_data.csv")
    print(f"Features: {list(df.columns)}")
    
    return df

if __name__ == "__main__":
    generate_training_data()
