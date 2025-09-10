# aether/apps/ai-core/simulator.py

import pandas as pd
import numpy as np

def generate_training_data(num_samples=2000):
    """Generates a comprehensive and realistic synthetic dataset."""
    
    # Base utilization
    utilization_gpu = np.random.randint(0, 101, size=num_samples)
    
    # Temp is correlated with utilization
    gpu_temp = (utilization_gpu * 0.4 + np.random.randint(35, 55, size=num_samples)).astype(int)
    
    # Power draw is correlated with utilization and temp
    power_draw_w = (utilization_gpu * 1.5 + gpu_temp * 0.5 + np.random.randint(50, 100, size=num_samples)).astype(int)

    data = {
        'utilization_gpu': utilization_gpu,
        'gpu_temp': gpu_temp,
        'power_draw_w': power_draw_w,
        'gpu_mem_used': np.random.randint(1000, 24000, size=num_samples),
        'job_type_training': np.random.randint(0, 2, size=num_samples),
        'throttling': np.zeros(num_samples, dtype=int), # Start with no throttling
        'good_placement': []
    }

    for i in range(num_samples):
        # --- Simulate Throttling ---
        # If temp is very high AND power is high, we simulate thermal throttling
        if data['gpu_temp'][i] > 90 and data['power_draw_w'][i] > 350:
            data['throttling'][i] = 1 # 1 means thermal throttling is active
    
        # --- Determine Outcome ---
        is_throttling = data['throttling'][i] == 1
        is_training = data['job_type_training'][i] == 1
        
        # A good placement is one that AVOIDS throttling
        # Training jobs are more sensitive and should not be placed on hot/busy GPUs
        if is_throttling:
            data['good_placement'].append(0) # Never good to place on a throttling GPU
        elif is_training and data['gpu_temp'][i] > 75:
            data['good_placement'].append(0) # Too hot for a heavy training job
        elif data['gpu_mem_used'][i] > 22000:
             data['good_placement'].append(0) # Not enough memory
        else:
            data['good_placement'].append(1)

    df = pd.DataFrame(data)
    df.to_csv('training_data.csv', index=False)
    print(f"Generated {num_samples} new samples and saved to training_data.csv")

if __name__ == "__main__":
    generate_training_data()
