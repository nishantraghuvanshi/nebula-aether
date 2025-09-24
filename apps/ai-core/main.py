# aether/apps/ai-core/main.py
# Enhanced AI Core with multi-candidate GPU scheduling and context-aware decision making

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import joblib
import pandas as pd
import numpy as np
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Aether AI Core", description="Intelligent GPU job scheduling service")

# Load the trained model
try:
    model = joblib.load('scheduler_model.pkl')
    logger.info("Successfully loaded scheduler model")
except Exception as e:
    logger.error(f"Failed to load model: {e}")
    model = None

class GpuCandidate(BaseModel):
    """Individual GPU candidate for job placement evaluation - matches Go orchestrator format"""
    gpu_id: str
    gpu_temp: int
    gpu_mem_used: int
    gpu_mem_total: int                    # NEW: Total VRAM for constraint checking
    utilization_gpu: int
    power_draw_w: int
    throttling_reasons: str
    # NEW: Enhanced GPU information
    gpu_vendor: Optional[str] = "Unknown"
    gpu_architecture: Optional[str] = "Unknown"

class PredictionRequest(BaseModel):
    """Enhanced prediction request with job context and multiple GPU candidates"""
    candidates: List[GpuCandidate]        # All viable GPU candidates (pre-filtered)
    job_type: str                         # "training" or "inference"
    # NEW: Job context for intelligent scheduling
    vram_required_mb: int                 # VRAM requirement in MB
    gpu_count: int = 1                    # Number of GPUs needed
    priority: int = 0                     # Job priority (0-10)
    user_id: Optional[str] = None         # User context
    tenant_id: Optional[str] = None       # Tenant context
    expected_duration: Optional[str] = None  # "short", "medium", "long"
    compute_intensity: Optional[str] = None  # "compute-bound", "memory-bound", "io-bound"

class PredictionResponse(BaseModel):
    """Enhanced prediction response with detailed decision context"""
    best_gpu_ids: List[str]              # Selected GPU IDs (supports multi-GPU)
    confidence: float                     # Confidence score (0.0-1.0)
    reason_code: str                     # Human-readable decision reason
    failure_reason: Optional[str] = None  # Why placement failed (if any)

def extract_features(candidates: List[GpuCandidate], request: PredictionRequest) -> pd.DataFrame:
    """Extract ML features from GPU candidates and job context"""
    features = []
    
    for candidate in candidates:
        # Calculate derived features
        mem_available_after_job = (candidate.gpu_mem_total - candidate.gpu_mem_used) - request.vram_required_mb
        mem_utilization_percent = (candidate.gpu_mem_used / candidate.gpu_mem_total) * 100 if candidate.gpu_mem_total > 0 else 0
        
        # Check for throttling
        is_throttling = 1 if (candidate.throttling_reasons and 
                             candidate.throttling_reasons not in ["", "None", "[]"]) else 0
        
        # Job type encoding
        is_training = 1 if request.job_type == 'training' else 0
        
        # Vendor encoding (one-hot)
        vendor_nvidia = 1 if candidate.gpu_vendor == "NVIDIA" else 0
        vendor_amd = 1 if candidate.gpu_vendor == "AMD" else 0
        vendor_intel = 1 if candidate.gpu_vendor == "Intel" else 0
        vendor_apple = 1 if candidate.gpu_vendor == "Apple" else 0
        
        # Temperature efficiency score (lower is better)
        temp_efficiency = max(0, 100 - candidate.gpu_temp) / 100
        
        # Power efficiency score (consider utilization vs power draw)
        power_efficiency = candidate.utilization_gpu / max(candidate.power_draw_w, 1)
        
        feature_dict = {
            # Core GPU metrics
            'gpu_temp': candidate.gpu_temp,
            'gpu_mem_used': candidate.gpu_mem_used,
            'gpu_mem_total': candidate.gpu_mem_total,
            'utilization_gpu': candidate.utilization_gpu,
            'power_draw_w': candidate.power_draw_w,
            
            # Derived features
            'mem_available_after_job': mem_available_after_job,
            'mem_utilization_percent': mem_utilization_percent,
            'temp_efficiency': temp_efficiency,
            'power_efficiency': power_efficiency,
            
            # Job context
            'vram_required_mb': request.vram_required_mb,
            'job_type_training': is_training,
            'priority': request.priority,
            
            # GPU characteristics
            'is_throttling': is_throttling,
            'vendor_nvidia': vendor_nvidia,
            'vendor_amd': vendor_amd,
            'vendor_intel': vendor_intel,
            'vendor_apple': vendor_apple,
        }
        features.append(feature_dict)
    
    return pd.DataFrame(features)

def score_gpu_candidates(candidates: List[GpuCandidate], request: PredictionRequest) -> List[tuple]:
    """Score GPU candidates using heuristic rules when ML model is unavailable"""
    scored_candidates = []
    
    for candidate in candidates:
        score = 100.0  # Start with perfect score
        
        # Memory availability (higher available memory = better score)
        mem_available = candidate.gpu_mem_total - candidate.gpu_mem_used
        mem_ratio = mem_available / request.vram_required_mb if request.vram_required_mb > 0 else 1
        if mem_ratio < 1.5:  # Less than 1.5x required memory
            score *= 0.8
        elif mem_ratio > 3:  # More than 3x required memory
            score *= 1.1
        
        # Temperature penalty (cooler GPUs preferred)
        if candidate.gpu_temp > 80:
            score *= 0.7
        elif candidate.gpu_temp > 70:
            score *= 0.9
        elif candidate.gpu_temp < 60:
            score *= 1.1
        
        # Utilization preference (prefer less utilized GPUs)
        if candidate.utilization_gpu > 80:
            score *= 0.8
        elif candidate.utilization_gpu < 30:
            score *= 1.1
        
        # Power efficiency (lower power draw for same utilization is better)
        if candidate.power_draw_w > 300:  # High power consumption
            score *= 0.9
        
        # Vendor preferences for different job types
        if request.job_type == "training" and candidate.gpu_vendor == "NVIDIA":
            score *= 1.1  # NVIDIA preferred for training
        elif request.job_type == "inference" and candidate.gpu_vendor == "Apple":
            score *= 1.05  # Apple Silicon efficient for inference
        
        # Throttling penalty
        if candidate.throttling_reasons and candidate.throttling_reasons not in ["", "None", "[]"]:
            score *= 0.5  # Heavy penalty for throttling
        
        scored_candidates.append((candidate.gpu_id, score, candidate))
    
    # Sort by score (descending)
    scored_candidates.sort(key=lambda x: x[1], reverse=True)
    return scored_candidates

@app.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest):
    """
    Intelligent GPU job placement decision making
    
    This endpoint evaluates multiple GPU candidates and selects the best one(s)
    for job placement based on ML model predictions or heuristic scoring.
    """
    
    try:
        logger.info(f"Received prediction request for job type: {request.job_type}, "
                   f"candidates: {len(request.candidates)}, VRAM needed: {request.vram_required_mb} MB")
        
        if not request.candidates:
            return PredictionResponse(
                best_gpu_ids=[],
                confidence=0.0,
                reason_code="No viable candidates",
                failure_reason="No GPU candidates provided after pre-filtering"
            )
        
        # Use ML model if available, otherwise fall back to heuristic scoring
        if model is not None:
            try:
                # Extract features for ML prediction
                features_df = extract_features(request.candidates, request)
                
                # Get predictions for all candidates
                predictions = model.predict_proba(features_df)
                
                # Score candidates based on ML predictions
                candidate_scores = []
                for i, candidate in enumerate(request.candidates):
                    # Assume model predicts probability of good placement
                    good_placement_prob = predictions[i][1] if len(predictions[i]) > 1 else predictions[i][0]
                    candidate_scores.append((candidate.gpu_id, good_placement_prob, candidate))
                
                # Sort by ML prediction score
                candidate_scores.sort(key=lambda x: x[1], reverse=True)
                
                best_gpu_id = candidate_scores[0][0]
                confidence = float(candidate_scores[0][1])
                reason_code = f"ML model selected based on {confidence:.2f} confidence"
                
                logger.info(f"ML model prediction: {best_gpu_id} with confidence {confidence:.2f}")
                
            except Exception as e:
                logger.warning(f"ML model prediction failed: {e}, falling back to heuristics")
                # Fall back to heuristic scoring
                candidate_scores = score_gpu_candidates(request.candidates, request)
                best_gpu_id = candidate_scores[0][0]
                confidence = min(candidate_scores[0][1] / 100.0, 1.0)  # Normalize to 0-1
                reason_code = f"Heuristic scoring selected (ML fallback)"
        else:
            # Use heuristic scoring
            candidate_scores = score_gpu_candidates(request.candidates, request)
            best_gpu_id = candidate_scores[0][0]
            confidence = min(candidate_scores[0][1] / 100.0, 1.0)  # Normalize to 0-1
            reason_code = "Heuristic scoring selected"
            
            logger.info(f"Heuristic prediction: {best_gpu_id} with score {candidate_scores[0][1]:.2f}")
        
        # For now, return single GPU (multi-GPU support can be added later)
        return PredictionResponse(
            best_gpu_ids=[best_gpu_id],
            confidence=confidence,
            reason_code=reason_code
        )
        
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "service": "Aether AI Core"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
