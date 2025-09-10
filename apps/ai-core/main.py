# aether/apps/ai-core/main.py

from fastapi import FastAPI
from pydantic import BaseModel
import joblib
import pandas as pd

app = FastAPI()
model = joblib.load('scheduler_model.pkl')

class PredictionRequest(BaseModel):
    gpu_temp: int
    gpu_mem_used: int
    job_type: str  # "training" or "inference"
    utilization_gpu: int
    power_draw_w: int
    throttling_reasons: str # We'll convert this to a simple 0 or 1

@app.post("/predict")
def predict(request: PredictionRequest):
    # Prepare the input for the new model
    is_training = 1 if request.job_type == 'training' else 0
    # A simple way to check for throttling: if the string isn't empty or 'None'
    is_throttling = 1 if request.throttling_reasons and request.throttling_reasons != "[]" else 0
    
    data = {
        'gpu_temp': [request.gpu_temp],
        'gpu_mem_used': [request.gpu_mem_used],
        'job_type_training': [is_training],
        'utilization_gpu': [request.utilization_gpu],
        'power_draw_w': [request.power_draw_w],
        'throttling': [is_throttling]
    }
    df = pd.DataFrame(data)

    prediction = model.predict(df)
    is_good_placement = bool(prediction[0])

    return {"is_good_placement": is_good_placement}
