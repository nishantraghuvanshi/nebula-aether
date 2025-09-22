# aether/apps/ai-core/main.py

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
import joblib
import pandas as pd
import os

app = FastAPI()

# Enhanced GPU Candidate with all telemetry features
class GpuCandidate(BaseModel):
    gpu_id: str
    gpu_name: str

    # Core telemetry
    gpu_temp: int
    gpu_mem_used: int
    gpu_mem_total: int
    utilization_gpu: int
    utilization_memory_controller: int
    power_draw_w: int
    throttling_reasons: str

    # Clock speeds
    clock_gpu_mhz: int
    clock_mem_mhz: int

    # Performance state
    performance_state: str

# Job requirements for enhanced scheduling
class JobRequirements(BaseModel):
    min_memory_mb: int = 0
    expected_gpu_util: int = 50
    max_duration_sec: int = 300
    priority: str = "normal"  # "low", "normal", "high"
    compute_intensity: str = "mixed"  # "memory", "compute", "mixed"

class PredictionRequest(BaseModel):
    candidates: List[GpuCandidate]
    job_type: str  # "training", "inference", "compute", "memory"
    job_requirements: Optional[JobRequirements] = None

class PredictionResponse(BaseModel):
    best_gpu_id: str
    confidence_score: float
    predicted_performance: float
    thermal_risk: float
    memory_risk: float
    reasons: List[str]

# Enhanced Model manager for different job types
class ModelManager:
    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.load_models()

    def load_models(self):
        model_files = {
            'general': 'scheduler_model.pkl',
            'training': 'training_model.pkl',
            'inference': 'inference_model.pkl',
            'compute': 'compute_model.pkl',
            'memory': 'memory_model.pkl'
        }

        scaler_files = {
            'general': 'scheduler_scaler.pkl',
            'training': 'training_scaler.pkl',
            'inference': 'inference_scaler.pkl',
            'compute': 'compute_scaler.pkl',
            'memory': 'memory_scaler.pkl'
        }

        for job_type, filename in model_files.items():
            if os.path.exists(filename):
                try:
                    self.models[job_type] = joblib.load(filename)
                    print(f"Loaded {job_type} model from {filename}")

                    # Load corresponding scaler
                    scaler_file = scaler_files.get(job_type)
                    if scaler_file and os.path.exists(scaler_file):
                        self.scalers[job_type] = joblib.load(scaler_file)
                        print(f"Loaded {job_type} scaler from {scaler_file}")
                    else:
                        print(f"Scaler file {scaler_file} not found for {job_type}")

                except Exception as e:
                    print(f"Failed to load {job_type} model: {e}")
            else:
                print(f"Model file {filename} not found")

        # Ensure we have at least the general model
        if 'general' not in self.models and os.path.exists('scheduler_model.pkl'):
            self.models['general'] = joblib.load('scheduler_model.pkl')
            if os.path.exists('scheduler_scaler.pkl'):
                self.scalers['general'] = joblib.load('scheduler_scaler.pkl')

    def get_model_and_scaler(self, job_type):
        model = self.models.get(job_type, self.models.get('general'))
        scaler = self.scalers.get(job_type, self.scalers.get('general'))
        return model, scaler

model_manager = ModelManager()

def calculate_derived_features(candidate: GpuCandidate, job_requirements: Optional[JobRequirements] = None):
    """Calculate enhanced features from raw telemetry"""
    features = {}

    # Memory efficiency
    features['memory_utilization_pct'] = (candidate.gpu_mem_used / max(candidate.gpu_mem_total, 1)) * 100

    # Thermal headroom (assuming 83°C thermal limit)
    features['thermal_headroom'] = max(83 - candidate.gpu_temp, 0)

    # Power efficiency
    features['power_per_util'] = candidate.power_draw_w / max(candidate.utilization_gpu, 1)

    # Clock efficiency ratios (normalized)
    features['gpu_clock_ratio'] = candidate.clock_gpu_mhz / 2000.0  # Normalize to typical base clock
    features['mem_clock_ratio'] = candidate.clock_mem_mhz / 6000.0  # Normalize to typical memory clock

    # Performance state numeric
    try:
        features['perf_state_numeric'] = int(candidate.performance_state[1:]) if candidate.performance_state.startswith('P') else 0
    except:
        features['perf_state_numeric'] = 0

    # Throttling binary
    features['is_throttling'] = 1 if candidate.throttling_reasons and candidate.throttling_reasons not in ["", "None", "[]"] else 0

    # Job compatibility features
    if job_requirements:
        features['memory_sufficient'] = 1 if (candidate.gpu_mem_total - candidate.gpu_mem_used) >= job_requirements.min_memory_mb else 0
        features['expected_util_match'] = 1 - abs(candidate.utilization_gpu - job_requirements.expected_gpu_util) / 100.0

        # Priority weighting
        priority_weights = {'low': 0.5, 'normal': 1.0, 'high': 1.5}
        features['priority_weight'] = priority_weights.get(job_requirements.priority, 1.0)
    else:
        features['memory_sufficient'] = 1
        features['expected_util_match'] = 1.0
        features['priority_weight'] = 1.0

    return features

def evaluate_gpu_candidate(candidate: GpuCandidate, job_type: str, job_requirements: Optional[JobRequirements], model, scaler):
    """Enhanced GPU evaluation with multi-criteria scoring"""

    # Get derived features
    derived = calculate_derived_features(candidate, job_requirements)

    # Prepare feature vector
    feature_data = {
        # Core telemetry
        'utilization_gpu': [candidate.utilization_gpu],
        'gpu_temp': [candidate.gpu_temp],
        'power_draw_w': [candidate.power_draw_w],
        'gpu_mem_used': [candidate.gpu_mem_used],
        'gpu_mem_total': [candidate.gpu_mem_total],
        'utilization_memory_controller': [candidate.utilization_memory_controller],
        'clock_gpu_mhz': [candidate.clock_gpu_mhz],
        'clock_mem_mhz': [candidate.clock_mem_mhz],

        # Job type encoding
        'job_type_training': [1 if job_type == 'training' else 0],
        'job_type_inference': [1 if job_type == 'inference' else 0],
        'job_type_compute': [1 if job_type == 'compute' else 0],
        'job_type_memory': [1 if job_type == 'memory' else 0],

        # Derived features
        'memory_utilization_pct': [derived['memory_utilization_pct']],
        'thermal_headroom': [derived['thermal_headroom']],
        'power_per_util': [derived['power_per_util']],
        'gpu_clock_ratio': [derived['gpu_clock_ratio']],
        'mem_clock_ratio': [derived['mem_clock_ratio']],
        'perf_state_numeric': [derived['perf_state_numeric']],
        'is_throttling': [derived['is_throttling']],
        'memory_sufficient': [derived['memory_sufficient']],
        'expected_util_match': [derived['expected_util_match']],
        'priority_weight': [derived['priority_weight']]
    }

    df = pd.DataFrame(feature_data)

    try:
        # Scale features
        df_scaled = scaler.transform(df)

        # Get multi-output predictions from enhanced model
        # Returns: [performance_score (0-100), thermal_risk (0-1), memory_risk (0-1)]
        predictions = model.predict(df_scaled)[0]

        performance_score = float(predictions[0])  # Performance score (0-100)
        thermal_risk = float(predictions[1])       # Thermal risk (0-1)
        memory_risk = float(predictions[2])        # Memory risk (0-1)

        # Apply compatibility penalties to performance score
        if job_requirements:
            if not derived['memory_sufficient']:
                performance_score *= 0.1  # Heavy penalty for insufficient memory

            # Penalize poor utilization match
            performance_score *= derived['expected_util_match']

        # Apply current state penalties
        if derived['is_throttling']:
            performance_score *= 0.7  # Penalty for current throttling

        # Ensure bounds
        performance_score = max(0, min(100, performance_score))
        thermal_risk = max(0, min(1, thermal_risk))
        memory_risk = max(0, min(1, memory_risk))

        return {
            'performance_score': performance_score,
            'thermal_risk': thermal_risk,
            'memory_risk': memory_risk,
            'derived_features': derived
        }

    except Exception as e:
        print(f"Error evaluating GPU {candidate.gpu_id}: {e}")
        return {
            'performance_score': 0.0,
            'thermal_risk': 1.0,
            'memory_risk': 1.0,
            'derived_features': derived
        }

@app.post("/predict")
def predict(request: PredictionRequest) -> PredictionResponse:
    if not request.candidates:
        return PredictionResponse(
            best_gpu_id="",
            confidence_score=0.0,
            predicted_performance=0.0,
            thermal_risk=1.0,
            memory_risk=1.0,
            reasons=["No GPU candidates available"]
        )

    # Get appropriate model and scaler for job type
    model, scaler = model_manager.get_model_and_scaler(request.job_type)
    if model is None or scaler is None:
        return PredictionResponse(
            best_gpu_id="",
            confidence_score=0.0,
            predicted_performance=0.0,
            thermal_risk=1.0,
            memory_risk=1.0,
            reasons=["No suitable model or scaler available"]
        )

    # Evaluate all GPU candidates
    gpu_evaluations = []

    for candidate in request.candidates:
        evaluation = evaluate_gpu_candidate(candidate, request.job_type, request.job_requirements, model, scaler)
        gpu_evaluations.append((candidate.gpu_id, evaluation))

    # Select best GPU
    best_gpu_id, best_eval = max(gpu_evaluations, key=lambda x: x[1]['performance_score'])

    # Generate selection reasons
    reasons = []
    for gpu_id, eval_data in gpu_evaluations:
        score = eval_data['performance_score']
        if gpu_id == best_gpu_id:
            reasons.append(f"Selected {gpu_id}: {score:.1f}% performance score")
            if eval_data['thermal_risk'] < 0.3:
                reasons.append(f"  ✓ Good thermal conditions ({eval_data['derived_features']['thermal_headroom']:.0f}°C headroom)")
            if eval_data['memory_risk'] < 0.3:
                reasons.append(f"  ✓ Good memory availability ({100-eval_data['derived_features']['memory_utilization_pct']:.1f}% free)")
        else:
            reasons.append(f"Rejected {gpu_id}: {score:.1f}% performance score")

    print(f"GPU Selection Results:")
    for reason in reasons:
        print(f"  {reason}")

    return PredictionResponse(
        best_gpu_id=best_gpu_id,
        confidence_score=best_eval['performance_score'] / 100.0,
        predicted_performance=best_eval['performance_score'],
        thermal_risk=best_eval['thermal_risk'],
        memory_risk=best_eval['memory_risk'],
        reasons=reasons
    )
