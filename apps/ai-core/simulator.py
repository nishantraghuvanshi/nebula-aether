import pandas as pd
import numpy as np

def generate_training_data(num_samples=1000):
    """Generates a synthetic dataset for training our scheduling model."""
    data = {
        'gpu_temp': np.random.randint(40, 95, size=num_samples),
        'gpu_mem_used': np.random.randint(1000, 24000, size=num_samples),
        'job_type_training': np.random.randint(0, 2, size=num_samples),
        # Outcome: 1 for good placement, 0 for bad (e.g., caused throttling)
        'good_placement': []
    }

    for i in range(num_samples):
        # Simple logic: a good placement happens if temp is low and memory is available
        temp = data['gpu_temp'][i]
        mem = data['gpu_mem_used'][i]
        is_training = data['job_type_training'][i]

        # Training jobs are more sensitive to heat
        heat_threshold = 75 if is_training else 85
        
        if temp < heat_threshold and mem < 20000:
            data['good_placement'].append(1)
        else:
            data['good_placement'].append(0)

    df = pd.DataFrame(data)
    df.to_csv('training_data.csv', index=False)
    print(f"Generated {num_samples} samples and saved to training_data.csv")

if __name__ == "__main__":
    generate_training_data()
