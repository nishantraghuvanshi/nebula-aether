# aether/apps/ai-core/main.py

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import joblib
import pandas as pd
import numpy as np

app = FastAPI()
model = joblib.load('scheduler_model.pkl')

class GpuCandidate(BaseModel):
    gpu_id: str
    gpu_temp: int
    gpu_mem_used: int
    utilization_gpu: int
    power_draw_w: int
    throttling_reasons: str

class PredictionRequest(BaseModel):
    candidates: List[GpuCandidate]
    job_type: str  # "training" or "inference"

class PredictionResponse(BaseModel):
    best_gpu_id: str

@app.post("/predict")
def predict(request: PredictionRequest) -> PredictionResponse:
    if not request.candidates:
        return PredictionResponse(best_gpu_id="")

    # Evaluate each GPU candidate
    scores = []
    gpu_ids = []

    for candidate in request.candidates:
        # Prepare features for this GPU
        is_training = 1 if request.job_type == 'training' else 0
        is_throttling = 1 if candidate.throttling_reasons and candidate.throttling_reasons not in ["", "None", "[]"] else 0

        data = {
            'gpu_temp': [candidate.gpu_temp],
            'gpu_mem_used': [candidate.gpu_mem_used],
            'job_type_training': [is_training],
            'utilization_gpu': [candidate.utilization_gpu],
            'power_draw_w': [candidate.power_draw_w],
            'throttling': [is_throttling]
        }
        df = pd.DataFrame(data)

        # Get prediction score (probability of good placement)
        try:
            if hasattr(model, 'predict_proba'):
                # For classifiers that support probability
                prob = model.predict_proba(df)[0][1]  # Probability of class 1 (good placement)
                scores.append(prob)
            else:
                # Fallback to binary prediction
                prediction = model.predict(df)[0]
                scores.append(float(prediction))
        except Exception as e:
            print(f"Error predicting for GPU {candidate.gpu_id}: {e}")
            scores.append(0.0)  # Worst score if prediction fails

        gpu_ids.append(candidate.gpu_id)

    # Select GPU with highest score
    best_idx = np.argmax(scores)
    best_gpu_id = gpu_ids[best_idx]

    print(f"GPU scores: {dict(zip(gpu_ids, scores))}")
    print(f"Selected GPU: {best_gpu_id}")

    return PredictionResponse(best_gpu_id=best_gpu_id)
