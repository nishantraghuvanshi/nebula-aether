from fastapi import FastAPI
from pydantic import BaseModel
import joblib
import pandas as pd

app = FastAPI()
model = joblib.load('scheduler_model.pkl')
anomaly_model = joblib.load('anomaly_detector.pkl')

class PredictionRequest(BaseModel):
    gpu_temp: int
    gpu_mem_used: int
    job_type: str # "training" or "inference"
    carbon_intensity: float = 300.0 # Default carbon intensity

class AnomalyRequest(BaseModel):
    gpu_temp: int
    gpu_mem_used: int

@app.post("/predict")
def predict(request: PredictionRequest):
    # Carbon-Aware Logic: If the job is heavy and carbon is high, deny placement
    is_heavy_job = request.job_type == 'training'
    is_carbon_high = request.carbon_intensity > 400 

    if is_heavy_job and is_carbon_high:
        return {"is_good_placement": False, "reason": "Carbon intensity is too high for a heavy job"}

    # Prepare the input for the model
    is_training = 1 if request.job_type == "training" else 0
    data = {
        'gpu_temp': [request.gpu_temp],
        'gpu_mem_used': [request.gpu_mem_used],
        'job_type_training': [is_training]
    }
    df = pd.DataFrame(data)

    # Make a prediction
    prediction = model.predict(df)
    is_good_placement = bool(prediction[0])
    reason = "OK" if is_good_placement else "GPU state not optimal"

    return {"is_good_placement": is_good_placement, "reason": reason}

@app.post("/anomaly")
def check_anomaly(request: AnomalyRequest):
    df = pd.DataFrame([{
        'gpu_temp': request.gpu_temp,
        'gpu_mem_used': request.gpu_mem_used
    }])
    
    # predict() returns 1 for inliers, -1 for outliers (anomalies)
    prediction = anomaly_model.predict(df)
    is_anomaly = bool(prediction[0] == -1)

    return {"is_anomaly": is_anomaly}
