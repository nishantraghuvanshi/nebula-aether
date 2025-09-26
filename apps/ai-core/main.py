# aether/apps/ai-core/main.py

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
import joblib
import pandas as pd
import os
import asyncio
import logging
from datetime import datetime
from training_pipeline import TrainingPipeline

app = FastAPI()

# Global training pipeline instance
training_pipeline = None
pipeline_task = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

    # Get appropriate model and scaler for job type (with A/B testing)
    model, scaler, model_version = model_manager.get_model_and_scaler(request.job_type)
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

    # Record prediction outcome for A/B testing evaluation
    predicted_performance = best_eval['performance_score']
    is_successful_prediction = predicted_performance >= 70.0  # Consider 70%+ as successful
    model_manager.record_prediction_outcome(model_version, predicted_performance, is_successful_prediction)

    # Log A/B testing usage
    if model_version and 'v' in model_version and not model_version.endswith('v1.0'):
        logger.info(f"🧪 A/B test prediction: {model_version} → {predicted_performance:.1f}% performance")

    return PredictionResponse(
        best_gpu_id=best_gpu_id,
        confidence_score=best_eval['performance_score'] / 100.0,
        predicted_performance=best_eval['performance_score'],
        thermal_risk=best_eval['thermal_risk'],
        memory_risk=best_eval['memory_risk'],
        reasons=reasons
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
            'password': os.getenv('DB_PASSWORD', 'aether123')
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
