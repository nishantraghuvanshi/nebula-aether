import pandas as pd
from sklearn.ensemble import IsolationForest
import joblib

# Use the same training data we generated earlier
df = pd.read_csv('training_data.csv')

# We'll train the detector on temperature and memory usage
X = df[['gpu_temp', 'gpu_mem_used']]

# The "contamination" parameter tells the model what percentage of data might be anomalies.
model = IsolationForest(contamination=0.05, random_state=42)
model.fit(X)

joblib.dump(model, 'anomaly_detector.pkl')
print("Anomaly detection model trained and saved to anomaly_detector.pkl")
