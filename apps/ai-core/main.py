# aether/apps/ai-core/main.py

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
import joblib
import pandas as pd
import os
import asyncio
import logging
import json
from datetime import datetime
from training_pipeline import TrainingPipeline

app = FastAPI()

# Global training pipeline instance
training_pipeline = None
pipeline_task = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enhanced logging system for AI Core
prediction_logger = None
scheduling_logger = None
error_logger = None

def init_ai_logging():
    """Initialize structured logging for AI Core decisions"""
    global prediction_logger, scheduling_logger, error_logger

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)

    # Prediction logging - detailed GPU evaluations and selections
    prediction_logger = logging.getLogger("ai_predictions")
    prediction_handler = logging.FileHandler(f"logs/ai_predictions_{timestamp}.log")
    prediction_formatter = logging.Formatter('%(message)s')
    prediction_handler.setFormatter(prediction_formatter)
    prediction_logger.addHandler(prediction_handler)
    prediction_logger.setLevel(logging.INFO)

    # Scheduling decision logging - queue/assign decisions with reasoning
    scheduling_logger = logging.getLogger("ai_scheduling")
    scheduling_handler = logging.FileHandler(f"logs/ai_scheduling_{timestamp}.log")
    scheduling_formatter = logging.Formatter('%(message)s')
    scheduling_handler.setFormatter(scheduling_formatter)
    scheduling_logger.addHandler(scheduling_handler)
    scheduling_logger.setLevel(logging.INFO)

    # Error and anomaly logging
    error_logger = logging.getLogger("ai_errors")
    error_handler = logging.FileHandler(f"logs/ai_errors_{timestamp}.log")
    error_formatter = logging.Formatter('%(message)s')
    error_handler.setFormatter(error_formatter)
    error_logger.addHandler(error_handler)
    error_logger.setLevel(logging.WARNING)

    # Log initialization
    log_structured(prediction_logger, "SYSTEM", "INIT", "AI prediction logging started", {})
    log_structured(scheduling_logger, "SYSTEM", "INIT", "AI scheduling logging started", {})
    log_structured(error_logger, "SYSTEM", "INIT", "AI error logging started", {})

    logger.info("📋 AI Core structured logging initialized")

def log_structured(log_instance, request_id, event, message, data):
    """Log structured JSON entries"""
    if log_instance:
        log_entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "request_id": request_id,
            "event": event,
            "message": message,
            "data": data
        }
        log_instance.info(json.dumps(log_entry))

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
    # NEW: Intelligent scheduling decisions
    scheduling_decision: str  # "assign_now", "queue_short", "queue_long"
    estimated_wait_time: int  # seconds
    resource_availability: Dict[str, float]  # Available memory, compute capacity
    scheduling_reason: str  # Why this scheduling decision was made

# Enhanced Model manager for different job types
class ModelManager:
    def __init__(self):
        self.models = {}          # Active models
        self.scalers = {}         # Active scalers
        self.testing_models = {}  # A/B testing models
        self.testing_scalers = {} # A/B testing scalers
        self.model_stats = {}     # Track A/B testing statistics
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

        # Load active models
        for job_type, filename in model_files.items():
            if os.path.exists(filename):
                try:
                    self.models[job_type] = joblib.load(filename)
                    logger.info(f"✅ Loaded {job_type} model from {filename}")

                    # Load corresponding scaler
                    scaler_file = scaler_files.get(job_type)
                    if scaler_file and os.path.exists(scaler_file):
                        self.scalers[job_type] = joblib.load(scaler_file)
                        logger.info(f"✅ Loaded {job_type} scaler from {scaler_file}")
                    else:
                        logger.warning(f"⚠️ Scaler file {scaler_file} not found for {job_type}")
                except Exception as e:
                    logger.error(f"❌ Failed to load {job_type} model: {e}")
            else:
                logger.warning(f"⚠️ Model file {filename} not found")

        # Ensure we have at least the general model
        if 'general' not in self.models and os.path.exists('scheduler_model.pkl'):
            self.models['general'] = joblib.load('scheduler_model.pkl')
            if os.path.exists('scheduler_scaler.pkl'):
                self.scalers['general'] = joblib.load('scheduler_scaler.pkl')

        # Load testing models (versioned files)
        self.load_testing_models()

    def load_testing_models(self):
        """Load models that are in A/B testing"""
        import glob

        # Find versioned model files (e.g., training_model_v123456.pkl)
        testing_files = glob.glob("*_model_v*.pkl")

        for test_file in testing_files:
            try:
                # Parse model info from filename
                base_name = test_file.replace('.pkl', '')
                parts = base_name.split('_')
                if len(parts) >= 3 and parts[-1].startswith('v'):
                    job_type = parts[0]  # e.g., 'training'
                    version = parts[-1]  # e.g., 'v123456'

                    # Load testing model
                    model = joblib.load(test_file)
                    model_key = f"{job_type}_{version}"
                    self.testing_models[model_key] = model

                    # Load corresponding testing scaler
                    scaler_file = test_file.replace('_model_', '_scaler_')
                    if os.path.exists(scaler_file):
                        self.testing_scalers[model_key] = joblib.load(scaler_file)
                        logger.info(f"🧪 Loaded A/B testing model: {model_key}")

                        # Initialize statistics
                        self.model_stats[model_key] = {
                            'predictions': 0,
                            'successes': 0,
                            'total_performance': 0.0
                        }

            except Exception as e:
                logger.error(f"❌ Failed to load testing model {test_file}: {e}")

    def get_model_and_scaler(self, job_type: str, request_id: str = None):
        """Get model and scaler with A/B testing support"""
        # Check if there's an A/B testing model for this job type
        testing_model_key = self.get_ab_testing_model(job_type)

        if testing_model_key and self.should_use_testing_model():
            # Use testing model
            model = self.testing_models.get(testing_model_key)
            scaler = self.testing_scalers.get(testing_model_key)

            if model and scaler:
                logger.info(f"🧪 Using A/B testing model: {testing_model_key}")
                return model, scaler, testing_model_key

        # Use active model (default)
        model = self.models.get(job_type, self.models.get('general'))
        scaler = self.scalers.get(job_type, self.scalers.get('general'))
        model_version = f"{job_type}_v1.0"  # Default version

        return model, scaler, model_version

    def get_ab_testing_model(self, job_type: str) -> Optional[str]:
        """Find A/B testing model for job type"""
        for model_key in self.testing_models.keys():
            if model_key.startswith(f"{job_type}_v"):
                return model_key
        return None

    def should_use_testing_model(self, ab_percentage: int = 20) -> bool:
        """Decide whether to use testing model based on A/B percentage"""
        import random
        return random.randint(1, 100) <= ab_percentage

    def record_prediction_outcome(self, model_version: str, performance_score: float, success: bool):
        """Record outcome for A/B testing evaluation"""
        if model_version in self.model_stats:
            stats = self.model_stats[model_version]
            stats['predictions'] += 1
            stats['total_performance'] += performance_score
            if success:
                stats['successes'] += 1

            # Log periodic statistics
            if stats['predictions'] % 10 == 0:
                avg_performance = stats['total_performance'] / stats['predictions']
                success_rate = stats['successes'] / stats['predictions']
                logger.info(f"📊 Model {model_version}: {stats['predictions']} predictions, "
                           f"{success_rate:.2%} success rate, {avg_performance:.1f} avg performance")

    def get_model_statistics(self) -> Dict:
        """Get A/B testing statistics for all models"""
        stats = {}
        for model_version, data in self.model_stats.items():
            if data['predictions'] > 0:
                stats[model_version] = {
                    'predictions': data['predictions'],
                    'success_rate': data['successes'] / data['predictions'],
                    'avg_performance': data['total_performance'] / data['predictions']
                }
        return stats

    def reload_models(self):
        """Reload all models (useful after training pipeline updates)"""
        logger.info("🔄 Reloading models...")
        self.models.clear()
        self.scalers.clear()
        self.testing_models.clear()
        self.testing_scalers.clear()
        self.load_models()

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

def select_best_gpu_with_load_balancing(gpu_evaluations, candidates):
    """Select best GPU with intelligent load balancing for equal scores"""
    # Get max score
    max_score = max(eval_data['performance_score'] for _, eval_data in gpu_evaluations)

    # Find all GPUs with the max score (within 1% tolerance)
    top_gpus = [(gpu_id, eval_data) for gpu_id, eval_data in gpu_evaluations
                if abs(eval_data['performance_score'] - max_score) <= 1.0]

    if len(top_gpus) == 1:
        # Only one best GPU, return it
        return top_gpus[0]

    print(f"🔄 Load balancing: {len(top_gpus)} GPUs tied at {max_score:.1f}% score")

    # Multiple GPUs tied - use load balancing criteria
    load_balancing_scores = []

    for gpu_id, eval_data in top_gpus:
        # Find the candidate object
        candidate = next(c for c in candidates if c.gpu_id == gpu_id)

        # Calculate load balancing score (lower is better)
        load_score = (
            candidate.utilization_gpu * 2.0 +  # Heavily weight current utilization
            candidate.utilization_memory_controller * 1.5 +
            (candidate.gpu_mem_used / candidate.gpu_mem_total) * 100 * 1.0 +
            candidate.gpu_temp * 0.5  # Lightly weight temperature
        )

        load_balancing_scores.append((gpu_id, eval_data, load_score))
        print(f"  {gpu_id}: utilization={candidate.utilization_gpu}%, memory={candidate.gpu_mem_used}MB, temp={candidate.gpu_temp}°C → load_score={load_score:.1f}")

    # Select GPU with lowest load score (least loaded)
    best_gpu_id, best_eval, best_load_score = min(load_balancing_scores, key=lambda x: x[2])
    print(f"🎯 Selected {best_gpu_id} (lowest load score: {best_load_score:.1f})")

    return best_gpu_id, best_eval

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

def make_scheduling_decision(best_candidate: GpuCandidate, job_requirements: Optional[JobRequirements],
                           best_eval: Dict) -> Dict[str, any]:
    """
    Intelligent scheduling decision based on resource availability and predicted conflicts
    Returns scheduling decision, wait time estimate, and reasoning
    """

    # Calculate resource availability
    memory_available_mb = best_candidate.gpu_mem_total - best_candidate.gpu_mem_used
    memory_utilization = (best_candidate.gpu_mem_used / best_candidate.gpu_mem_total) * 100
    gpu_utilization = best_candidate.utilization_gpu

    # Get job requirements (use defaults if not provided)
    required_memory = job_requirements.min_memory_mb if job_requirements else 1024
    expected_util = job_requirements.expected_gpu_util if job_requirements else 50
    max_duration = job_requirements.max_duration_sec if job_requirements else 300

    # Resource availability analysis
    resource_availability = {
        "available_memory_mb": float(memory_available_mb),
        "available_memory_pct": float(100 - memory_utilization),
        "available_compute_pct": float(100 - gpu_utilization),
        "thermal_headroom": float(85 - best_candidate.gpu_temp)  # Assume 85°C thermal limit
    }

    # INTELLIGENT SCHEDULING LOGIC

    # 1. Memory conflict detection
    memory_conflict = memory_available_mb < (required_memory * 1.2)  # 20% safety margin

    # 2. Compute conflict detection
    # Allow single jobs to use up to 100% of idle GPUs, only restrict when already busy
    if gpu_utilization < 10:  # Essentially idle GPU
        compute_conflict = expected_util > 100  # Only block if job needs >100%
    else:  # GPU already has work
        compute_conflict = (gpu_utilization + expected_util) > 85  # 85% max for multiple jobs

    # 3. Thermal conflict detection
    thermal_conflict = best_candidate.gpu_temp > 75 or "THERMAL" in best_candidate.throttling_reasons.upper()

    # 4. Multiple jobs detection (high utilization = likely other jobs running)
    likely_other_jobs = gpu_utilization > 30 and memory_utilization > 40

    # DECISION MATRIX

    # Safe to assign immediately - relaxed conditions for idle GPUs
    if (not memory_conflict and not compute_conflict and not thermal_conflict and
        gpu_utilization < 30 and memory_utilization < 80):
        return {
            "scheduling_decision": "assign_now",
            "estimated_wait_time": 0,
            "resource_availability": resource_availability,
            "scheduling_reason": f"✅ Resources available: {memory_available_mb}MB free, {100-gpu_utilization}% compute free, {85-best_candidate.gpu_temp}°C thermal headroom"
        }

    # Short wait (jobs likely to complete soon)
    elif likely_other_jobs and not thermal_conflict and max_duration < 600:
        estimated_wait = min(300, max_duration // 2)  # Estimate half duration of current jobs
        return {
            "scheduling_decision": "queue_short",
            "estimated_wait_time": estimated_wait,
            "resource_availability": resource_availability,
            "scheduling_reason": f"⏱️ Short queue: Current job likely finishing soon. Memory: {memory_available_mb}MB/{required_memory}MB needed, GPU: {gpu_utilization}% busy"
        }

    # Memory insufficient - longer wait needed
    elif memory_conflict:
        estimated_wait = max(300, max_duration)  # Wait for current job to complete
        return {
            "scheduling_decision": "queue_long",
            "estimated_wait_time": estimated_wait,
            "resource_availability": resource_availability,
            "scheduling_reason": f"🚫 Memory insufficient: Need {required_memory}MB, only {memory_available_mb}MB available. Wait for job completion."
        }

    # Compute overload - wait for current jobs
    elif compute_conflict:
        estimated_wait = max(180, max_duration // 3)  # Wait for some compute to free up
        return {
            "scheduling_decision": "queue_short",
            "estimated_wait_time": estimated_wait,
            "resource_availability": resource_availability,
            "scheduling_reason": f"⚡ Compute conflict: Current {gpu_utilization}% + expected {expected_util}% exceeds safe limit. Wait for resources."
        }

    # Thermal issues - wait for cooling
    elif thermal_conflict:
        estimated_wait = 120  # Wait for thermal conditions to improve
        return {
            "scheduling_decision": "queue_short",
            "estimated_wait_time": estimated_wait,
            "resource_availability": resource_availability,
            "scheduling_reason": f"🌡️ Thermal concern: {best_candidate.gpu_temp}°C temperature, throttling: {best_candidate.throttling_reasons}. Wait for cooling."
        }

    # Default to short queue for unknown conditions
    else:
        return {
            "scheduling_decision": "queue_short",
            "estimated_wait_time": 180,
            "resource_availability": resource_availability,
            "scheduling_reason": "⚠️ Conservative queuing: Resource utilization suggests waiting for better conditions"
        }

@app.post("/predict")
def predict(request: PredictionRequest) -> PredictionResponse:
    request_id = f"req_{datetime.now().strftime('%H%M%S')}_{len(request.candidates)}"
    if not request.candidates:
        # ENHANCED LOGGING: No candidates available
        log_structured(error_logger, request_id, "NO_CANDIDATES", "No GPU candidates available for prediction", {
            "job_type": request.job_type,
            "has_requirements": request.job_requirements is not None
        })

        return PredictionResponse(
            best_gpu_id="",
            confidence_score=0.0,
            predicted_performance=0.0,
            thermal_risk=1.0,
            memory_risk=1.0,
            reasons=["No GPU candidates available"],
            scheduling_decision="queue_long",
            estimated_wait_time=600,
            resource_availability={},
            scheduling_reason="No GPUs available for scheduling"
        )

    # Get appropriate model and scaler for job type (with A/B testing)
    model, scaler, model_version = model_manager.get_model_and_scaler(request.job_type)
    if model is None or scaler is None:
        # ENHANCED LOGGING: Model unavailable
        log_structured(error_logger, request_id, "MODEL_UNAVAILABLE", "No suitable model or scaler available", {
            "job_type": request.job_type,
            "model_available": model is not None,
            "scaler_available": scaler is not None,
            "candidates_count": len(request.candidates)
        })

        return PredictionResponse(
            best_gpu_id="",
            confidence_score=0.0,
            predicted_performance=0.0,
            thermal_risk=1.0,
            memory_risk=1.0,
            reasons=["No suitable model or scaler available"],
            scheduling_decision="queue_long",
            estimated_wait_time=600,
            resource_availability={},
            scheduling_reason="AI models not available for scheduling analysis"
        )

    # ENHANCED LOGGING: Start prediction process
    log_structured(prediction_logger, request_id, "PREDICTION_START", "Starting GPU evaluation process", {
        "job_type": request.job_type,
        "candidates_count": len(request.candidates),
        "model_version": model_version,
        "job_requirements": request.job_requirements.dict() if request.job_requirements else None,
        "candidates": [{
            "gpu_id": c.gpu_id,
            "gpu_name": c.gpu_name,
            "gpu_temp": c.gpu_temp,
            "gpu_util": c.utilization_gpu,
            "mem_used_mb": c.gpu_mem_used,
            "mem_total_mb": c.gpu_mem_total,
            "memory_util_pct": (c.gpu_mem_used / c.gpu_mem_total) * 100,
            "throttling": c.throttling_reasons
        } for c in request.candidates]
    })

    # Evaluate all GPU candidates
    gpu_evaluations = []

    for candidate in request.candidates:
        evaluation = evaluate_gpu_candidate(candidate, request.job_type, request.job_requirements, model, scaler)
        gpu_evaluations.append((candidate.gpu_id, evaluation))

        # ENHANCED LOGGING: Individual GPU evaluation
        log_structured(prediction_logger, request_id, "GPU_EVALUATED", f"Evaluated GPU {candidate.gpu_id}", {
            "gpu_id": candidate.gpu_id,
            "performance_score": evaluation['performance_score'],
            "thermal_risk": evaluation['thermal_risk'],
            "memory_risk": evaluation['memory_risk'],
            "derived_features": evaluation['derived_features']
        })

    # Select best GPU with load balancing for equal scores
    best_gpu_id, best_eval = select_best_gpu_with_load_balancing(gpu_evaluations, request.candidates)

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

    # NEW: Get the best candidate object for scheduling analysis
    best_candidate = next(c for c in request.candidates if c.gpu_id == best_gpu_id)

    # ENHANCED LOGGING: GPU selection results
    log_structured(prediction_logger, request_id, "GPU_SELECTION", f"Selected best GPU: {best_gpu_id}", {
        "best_gpu_id": best_gpu_id,
        "best_score": best_eval['performance_score'],
        "all_scores": {gpu_id: eval_data['performance_score'] for gpu_id, eval_data in gpu_evaluations},
        "performance_ranking": sorted([(gpu_id, eval_data['performance_score']) for gpu_id, eval_data in gpu_evaluations],
                                     key=lambda x: x[1], reverse=True)
    })

    # NEW: Make intelligent scheduling decision
    scheduling_info = make_scheduling_decision(best_candidate, request.job_requirements, best_eval)

    # ENHANCED LOGGING: Scheduling decision analysis
    log_structured(scheduling_logger, request_id, "SCHEDULING_DECISION", f"Made scheduling decision: {scheduling_info['scheduling_decision']}", {
        "job_type": request.job_type,
        "best_gpu_id": best_gpu_id,
        "scheduling_decision": scheduling_info['scheduling_decision'],
        "estimated_wait_time": scheduling_info['estimated_wait_time'],
        "scheduling_reason": scheduling_info['scheduling_reason'],
        "resource_availability": scheduling_info['resource_availability'],
        "gpu_state": {
            "temperature": best_candidate.gpu_temp,
            "gpu_utilization": best_candidate.utilization_gpu,
            "memory_used_mb": best_candidate.gpu_mem_used,
            "memory_total_mb": best_candidate.gpu_mem_total,
            "memory_utilization_pct": (best_candidate.gpu_mem_used / best_candidate.gpu_mem_total) * 100,
            "throttling_reasons": best_candidate.throttling_reasons
        },
        "job_requirements": {
            "min_memory_mb": request.job_requirements.min_memory_mb if request.job_requirements else 0,
            "expected_gpu_util": request.job_requirements.expected_gpu_util if request.job_requirements else 0,
            "max_duration_sec": request.job_requirements.max_duration_sec if request.job_requirements else 0,
            "priority": request.job_requirements.priority if request.job_requirements else "normal"
        }
    })

    # Add scheduling information to reasons
    reasons.append(f"🧠 Scheduling: {scheduling_info['scheduling_reason']}")

    # Record prediction outcome for A/B testing evaluation
    predicted_performance = best_eval['performance_score']
    is_successful_prediction = predicted_performance >= 70.0  # Consider 70%+ as successful
    model_manager.record_prediction_outcome(model_version, predicted_performance, is_successful_prediction)

    # Log A/B testing usage
    if model_version and 'v' in model_version and not model_version.endswith('v1.0'):
        logger.info(f"🧪 A/B test prediction: {model_version} → {predicted_performance:.1f}% performance")

    # Enhanced logging for scheduling decisions
    logger.info(f"🎯 Job Scheduling Decision: {best_gpu_id} → {scheduling_info['scheduling_decision']} "
                f"(wait: {scheduling_info['estimated_wait_time']}s)")

    # ENHANCED LOGGING: Final prediction response
    log_structured(prediction_logger, request_id, "PREDICTION_COMPLETE", "Prediction process completed", {
        "best_gpu_id": best_gpu_id,
        "confidence_score": best_eval['performance_score'] / 100.0,
        "predicted_performance": best_eval['performance_score'],
        "thermal_risk": best_eval['thermal_risk'],
        "memory_risk": best_eval['memory_risk'],
        "scheduling_decision": scheduling_info['scheduling_decision'],
        "estimated_wait_time": scheduling_info['estimated_wait_time'],
        "model_version": model_version,
        "total_candidates": len(request.candidates),
        "processing_time_ms": (datetime.now().timestamp() * 1000) % 1000  # Simple timing approximation
    })

    return PredictionResponse(
        best_gpu_id=best_gpu_id,
        confidence_score=best_eval['performance_score'] / 100.0,
        predicted_performance=best_eval['performance_score'],
        thermal_risk=best_eval['thermal_risk'],
        memory_risk=best_eval['memory_risk'],
        reasons=reasons,
        # NEW: Intelligent scheduling fields
        scheduling_decision=scheduling_info['scheduling_decision'],
        estimated_wait_time=scheduling_info['estimated_wait_time'],
        resource_availability=scheduling_info['resource_availability'],
        scheduling_reason=scheduling_info['scheduling_reason']
    )

# ==================== TRAINING PIPELINE ENDPOINTS ====================

class ModelVersionInfo(BaseModel):
    model_name: str
    version: str
    status: str
    accuracy: Optional[float] = None
    created_at: str
    deployment_percentage: Optional[int] = None

class TrainingStatus(BaseModel):
    pipeline_running: bool
    last_training_time: Optional[str] = None
    active_models: Dict[str, str]  # model_name -> version
    testing_models: List[ModelVersionInfo]
    total_training_samples: int

@app.get("/training/status", response_model=TrainingStatus)
async def get_training_status():
    """Get current training pipeline status"""
    global training_pipeline

    if training_pipeline is None:
        raise HTTPException(status_code=503, detail="Training pipeline not initialized")

    try:
        # Get active models
        active_models = {}
        for model_name, model_info in training_pipeline.models.items():
            active_models[model_name] = model_info.get('version', 'unknown')

        # Get testing models
        testing_models = []
        for model_key, model_info in training_pipeline.model_versions.items():
            if model_info.get('status') == 'testing':
                testing_models.append(ModelVersionInfo(
                    model_name=model_key.split('_')[0],
                    version=model_info['version'],
                    status=model_info['status'],
                    accuracy=model_info.get('accuracy'),
                    created_at=model_info['created_at'].isoformat(),
                    deployment_percentage=training_pipeline.training_config['ab_test_percentage']
                ))

        # Get total training samples (placeholder)
        total_samples = 0  # Would query database in real implementation

        return TrainingStatus(
            pipeline_running=pipeline_task is not None and not pipeline_task.done(),
            last_training_time=datetime.now().isoformat(),
            active_models=active_models,
            testing_models=testing_models,
            total_training_samples=total_samples
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting training status: {e}")

@app.post("/training/retrain/{model_name}")
async def trigger_manual_retrain(model_name: str, background_tasks: BackgroundTasks):
    """Manually trigger retraining for a specific model"""
    global training_pipeline

    if training_pipeline is None:
        raise HTTPException(status_code=503, detail="Training pipeline not initialized")

    if model_name not in training_pipeline.job_type_models.values():
        raise HTTPException(status_code=404, detail=f"Model {model_name} not found")

    try:
        # Trigger retraining in background
        background_tasks.add_task(manual_retrain_model, model_name)
        return {"message": f"Manual retraining triggered for {model_name}"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering retrain: {e}")

@app.post("/training/promote/{model_name}/{version}")
async def promote_model_version(model_name: str, version: str):
    """Promote a model version from testing to active"""
    global training_pipeline

    if training_pipeline is None:
        raise HTTPException(status_code=503, detail="Training pipeline not initialized")

    try:
        await training_pipeline.promote_model(model_name, version)
        return {"message": f"Model {model_name} version {version} promoted to active"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error promoting model: {e}")

@app.get("/training/models")
async def list_model_versions():
    """List all model versions and their status"""
    global training_pipeline

    if training_pipeline is None:
        raise HTTPException(status_code=503, detail="Training pipeline not initialized")

    models = []

    # Active models
    for model_name, model_info in training_pipeline.models.items():
        models.append(ModelVersionInfo(
            model_name=model_name,
            version=model_info.get('version', 'unknown'),
            status='active',
            created_at=model_info.get('created_at', datetime.now()).isoformat()
        ))

    # Testing models
    for model_key, model_info in training_pipeline.model_versions.items():
        models.append(ModelVersionInfo(
            model_name=model_key.split('_')[0],
            version=model_info['version'],
            status=model_info['status'],
            accuracy=model_info.get('accuracy'),
            created_at=model_info['created_at'].isoformat()
        ))

    return {"models": models}

@app.get("/training/ab-stats")
async def get_ab_testing_statistics():
    """Get A/B testing statistics for model evaluation"""
    global model_manager

    try:
        stats = model_manager.get_model_statistics()
        return {
            "ab_testing_stats": stats,
            "total_models_tested": len(stats),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting A/B stats: {e}")

@app.post("/training/reload-models")
async def reload_models():
    """Reload all models (useful after training pipeline creates new versions)"""
    global model_manager

    try:
        model_manager.reload_models()
        return {"message": "Models reloaded successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reloading models: {e}")

# ==================== STARTUP AND BACKGROUND TASKS ====================

async def manual_retrain_model(model_name: str):
    """Background task for manual retraining"""
    global training_pipeline

    try:
        logger.info(f"🔄 Manual retrain started for {model_name}")

        # Fetch recent data for this model's job types
        job_types = [job_type for job_type, model in training_pipeline.job_type_models.items()
                     if model == model_name]

        training_data = await training_pipeline.fetch_training_data()

        for job_type in job_types:
            job_data = training_data[training_data['job_type'] == job_type]
            if len(job_data) > 0:
                await training_pipeline.retrain_model(model_name, job_data, job_type)

        logger.info(f"✅ Manual retrain completed for {model_name}")

    except Exception as e:
        logger.error(f"❌ Manual retrain failed for {model_name}: {e}")

async def start_training_pipeline():
    """Start the training pipeline in background"""
    global training_pipeline, pipeline_task

    # Wait a bit for database to be ready
    await asyncio.sleep(5)

    try:
        # Database configuration
        db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', '5432')),
            'database': os.getenv('DB_NAME', 'aether'),
            'user': os.getenv('DB_USER', 'aether'),
            'password': os.getenv('DB_PASSWORD', 'aether')
        }

        # Initialize pipeline
        training_pipeline = TrainingPipeline(db_config)

        # Start pipeline in background
        pipeline_task = asyncio.create_task(training_pipeline.start_pipeline())
        logger.info("🚀 Training pipeline started successfully")

    except Exception as e:
        logger.error(f"❌ Failed to start training pipeline: {e}")
        logger.info("🔄 AI Core will continue running without training pipeline")
        training_pipeline = None

@app.on_event("startup")
async def startup_event():
    """FastAPI startup event"""
    logger.info("🚀 AI Core starting...")

    # Initialize comprehensive logging system
    init_ai_logging()

    # Check if training pipeline should be enabled
    enable_training = os.getenv('ENABLE_TRAINING_PIPELINE', 'true').lower() == 'true'

    if enable_training:
        logger.info("🧠 Training pipeline enabled - starting in background...")
        # Start training pipeline in background (non-blocking)
        asyncio.create_task(start_training_pipeline())
    else:
        logger.info("⚠️ Training pipeline disabled via environment variable")

    logger.info("✅ AI Core ready for predictions")

@app.on_event("shutdown")
async def shutdown_event():
    """FastAPI shutdown event"""
    global pipeline_task

    if pipeline_task and not pipeline_task.done():
        pipeline_task.cancel()
        logger.info("🛑 Training pipeline stopped")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "training_pipeline": pipeline_task is not None and not pipeline_task.done(),
        "timestamp": datetime.now().isoformat()
    }
