#!/usr/bin/env python3
"""
Dual-Mode AI Training Pipeline
Continuously collects performance data from job executions and retrains models
"""

import os
import json
import time
import logging
import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import joblib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, accuracy_score
import xgboost as xgb

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ModelVersion:
    """Represents a model version with metadata"""
    def __init__(self, name: str, version: str, model_type: str):
        self.name = name
        self.version = version
        self.model_type = model_type
        self.created_at = datetime.now()
        self.performance_metrics = {}
        self.deployment_status = 'training'  # training, testing, active, deprecated

class TrainingPipeline:
    """Main training pipeline that manages the dual-mode AI system"""

    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.conn = None
        self.models = {}  # current active models
        self.model_versions = {}  # version history
        self.training_config = {
            'retrain_interval_hours': 0.25,  # Retrain every 15 minutes
            'min_samples_for_training': 50,  # Minimum samples needed
            'ab_test_percentage': 20,  # 20% traffic for A/B testing
            'performance_threshold': 0.85,  # Model must achieve 85% accuracy
        }

        # Job type to model mapping
        self.job_type_models = {
            'training': 'training_model',
            'inference': 'inference_model',
            'compute': 'compute_model',
            'simulation': 'general_model',
            'analysis': 'general_model',
            'rendering': 'general_model',
            'mining': 'compute_model',
            'encoding': 'compute_model',
            'research': 'general_model',
            'development': 'general_model'
        }

    async def start_pipeline(self):
        """Start the continuous training pipeline"""
        logger.info("🚀 Starting dual-mode AI training pipeline...")

        # Connect to database
        await self.connect_database()

        # Load existing models
        await self.load_existing_models()

        # Start continuous training loop
        while True:
            try:
                # Check if retraining is needed
                if await self.should_retrain():
                    logger.info("📊 Starting model retraining cycle...")
                    await self.retrain_models()

                # Update model performance metrics
                await self.update_model_metrics()

                # Check for model promotion (A/B test results)
                await self.evaluate_ab_tests()

                # Wait before next cycle
                await asyncio.sleep(3600)  # Check every hour

            except Exception as e:
                logger.error(f"❌ Error in training pipeline: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error

    async def connect_database(self):
        """Connect to TimescaleDB with retries"""
        max_retries = 5
        retry_delay = 10

        for attempt in range(max_retries):
            try:
                self.conn = psycopg2.connect(**self.db_config)
                logger.info("✅ Connected to database")
                return
            except Exception as e:
                logger.error(f"❌ Database connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"⏳ Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error("❌ Failed to connect to database after all retries")
                    raise

    async def load_existing_models(self):
        """Load existing trained models"""
        model_files = [
            'training_model.pkl', 'inference_model.pkl', 'compute_model.pkl',
            'general_model.pkl', 'memory_model.pkl', 'anomaly_detector.pkl'
        ]

        for model_file in model_files:
            if os.path.exists(model_file):
                try:
                    model_name = model_file.replace('.pkl', '')
                    model = joblib.load(model_file)
                    scaler_file = model_name.replace('_model', '_scaler.pkl')
                    scaler = joblib.load(scaler_file) if os.path.exists(scaler_file) else None

                    self.models[model_name] = {
                        'model': model,
                        'scaler': scaler,
                        'version': 'v1.0',  # Default version
                        'created_at': datetime.now(),
                        'status': 'active'
                    }
                    logger.info(f"✅ Loaded model: {model_name}")
                except Exception as e:
                    logger.error(f"❌ Error loading model {model_file}: {e}")

    async def should_retrain(self) -> bool:
        """Determine if models need retraining"""
        try:
            cursor = self.conn.cursor(cursor_factory=RealDictCursor)

            # Check how much new training data is available
            cursor.execute("""
                SELECT COUNT(*) as new_samples
                FROM training_data
                WHERE created_at > NOW() - INTERVAL '%d hours'
            """, (self.training_config['retrain_interval_hours'],))

            result = cursor.fetchone()
            new_samples = result['new_samples'] if result else 0

            logger.info(f"📊 New training samples available: {new_samples}")

            return new_samples >= self.training_config['min_samples_for_training']

        except Exception as e:
            logger.error(f"❌ Error checking training data: {e}")
            return False

    async def retrain_models(self):
        """Retrain models with latest performance data"""
        try:
            # Fetch latest training data
            training_data = await self.fetch_training_data()

            if len(training_data) < self.training_config['min_samples_for_training']:
                logger.warning("⚠️ Insufficient training data for retraining")
                return

            # Group by job type and retrain each model
            for job_type, model_name in self.job_type_models.items():
                job_data = training_data[training_data['job_type'] == job_type]

                if len(job_data) >= 20:  # Minimum per job type
                    await self.retrain_model(model_name, job_data, job_type)

        except Exception as e:
            logger.error(f"❌ Error in retraining: {e}")

    async def fetch_training_data(self) -> pd.DataFrame:
        """Fetch training data from database"""
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)

        # Fetch comprehensive job performance data
        cursor.execute("""
            SELECT
                jp.job_type,
                jp.gpu_id,
                jp.duration_seconds,
                jp.throughput,
                jp.performance_score,
                jp.resource_efficiency,
                jp.thermal_impact,
                jp.power_efficiency,
                jp.reliability_score,
                jp.avg_gpu_utilization,
                jp.max_gpu_utilization,
                jp.avg_memory_utilization,
                jp.avg_temperature,
                jp.max_temperature,
                jp.avg_power_draw,
                td.features,
                td.labels
            FROM job_performance jp
            JOIN training_data td ON jp.job_id = td.job_id
            WHERE jp.created_at > NOW() - INTERVAL '7 days'
            AND jp.performance_score IS NOT NULL
            ORDER BY jp.created_at DESC
        """)

        rows = cursor.fetchall()
        return pd.DataFrame(rows)

    async def retrain_model(self, model_name: str, data: pd.DataFrame, job_type: str):
        """Retrain a specific model with new data"""
        logger.info(f"🔄 Retraining {model_name} for {job_type} jobs with {len(data)} samples")

        try:
            # Prepare features and targets
            X, y = self.prepare_training_data(data)

            if len(X) == 0:
                logger.warning(f"⚠️ No valid training data for {model_name}")
                return

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            # Train new model version
            new_model = xgb.XGBRegressor(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42
            )

            new_model.fit(X_train_scaled, y_train)

            # Evaluate model
            y_pred = new_model.predict(X_test_scaled)
            mse = mean_squared_error(y_test, y_pred)
            accuracy = 1 - (mse / np.var(y_test))  # Pseudo R²

            logger.info(f"📊 Model performance: MSE={mse:.4f}, Accuracy={accuracy:.4f}")

            # Check if model meets performance threshold
            if accuracy >= self.training_config['performance_threshold']:
                # Create new model version
                new_version = f"v{int(time.time())}"  # Timestamp-based version

                # Save model for A/B testing
                test_model_path = f"{model_name}_{new_version}.pkl"
                test_scaler_path = f"{model_name.replace('_model', '_scaler')}_{new_version}.pkl"

                joblib.dump(new_model, test_model_path)
                joblib.dump(scaler, test_scaler_path)

                # Store in model versions for A/B testing
                self.model_versions[f"{model_name}_{new_version}"] = {
                    'model': new_model,
                    'scaler': scaler,
                    'version': new_version,
                    'job_type': job_type,
                    'accuracy': accuracy,
                    'created_at': datetime.now(),
                    'status': 'testing',  # Ready for A/B testing
                    'test_file': test_model_path
                }

                # Record in database
                await self.record_model_deployment(model_name, new_version, 'ab_test',
                                                   self.training_config['ab_test_percentage'])

                logger.info(f"✅ New model version {new_version} ready for A/B testing")
            else:
                logger.warning(f"⚠️ New model accuracy {accuracy:.4f} below threshold {self.training_config['performance_threshold']}")

        except Exception as e:
            logger.error(f"❌ Error retraining {model_name}: {e}")

    def prepare_training_data(self, data: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare features and targets from raw data"""
        features = []
        targets = []

        for _, row in data.iterrows():
            try:
                # Parse features JSON
                feature_dict = json.loads(row['features']) if isinstance(row['features'], str) else row['features']

                # Parse labels JSON
                label_dict = json.loads(row['labels']) if isinstance(row['labels'], str) else row['labels']

                # Create feature vector
                feature_vector = [
                    row['avg_gpu_utilization'] or 0.5,
                    row['avg_memory_utilization'] or 0.5,
                    row['avg_temperature'] or 75,
                    row['avg_power_draw'] or 200,
                    row['duration_seconds'] or 300,
                    hash(row['job_type']) % 1000 / 1000.0,  # Job type encoding
                ]

                # Target is performance score
                target = row['performance_score'] or 50.0

                features.append(feature_vector)
                targets.append(target)

            except Exception as e:
                logger.warning(f"⚠️ Skipping invalid training sample: {e}")
                continue

        return np.array(features), np.array(targets)

    async def record_model_deployment(self, model_name: str, version: str,
                                      deployment_type: str, percentage: int):
        """Record model deployment in database"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO model_deployments
                (model_name, model_version, deployment_type, deployment_percentage)
                VALUES (%s, %s, %s, %s)
            """, (model_name, version, deployment_type, percentage))
            self.conn.commit()

        except Exception as e:
            logger.error(f"❌ Error recording deployment: {e}")

    async def update_model_metrics(self):
        """Update model performance metrics"""
        try:
            cursor = self.conn.cursor(cursor_factory=RealDictCursor)

            # Get recent predictions vs actual performance
            cursor.execute("""
                SELECT model_version_used,
                       AVG(performance_score) as avg_performance
                FROM training_data
                WHERE created_at > NOW() - INTERVAL '1 day'
                AND model_version_used IS NOT NULL
                GROUP BY model_version_used
            """)

            results = cursor.fetchall()
            for result in results:
                model_version = result['model_version_used']
                performance = result['avg_performance']

                # Update model_performance table
                cursor.execute("""
                    INSERT INTO model_performance
                    (model_name, model_version, job_type, prediction_accuracy, evaluation_date)
                    VALUES (%s, %s, 'mixed', %s, NOW())
                    ON CONFLICT (model_name, model_version) DO UPDATE SET
                    prediction_accuracy = EXCLUDED.prediction_accuracy,
                    evaluation_date = EXCLUDED.evaluation_date
                """, (model_version.split('_')[0], model_version, performance / 100.0))

            self.conn.commit()

        except Exception as e:
            logger.error(f"❌ Error updating model metrics: {e}")

    async def evaluate_ab_tests(self):
        """Evaluate A/B test results and promote successful models"""
        try:
            cursor = self.conn.cursor(cursor_factory=RealDictCursor)

            # Find models in A/B testing
            cursor.execute("""
                SELECT model_name, model_version, total_predictions, success_rate
                FROM model_deployments
                WHERE deployment_type = 'ab_test'
                AND total_predictions >= 100  -- Minimum predictions for evaluation
            """)

            ab_models = cursor.fetchall()

            for model_info in ab_models:
                model_key = f"{model_info['model_name']}_{model_info['model_version']}"

                if model_key in self.model_versions:
                    success_rate = model_info['success_rate'] or 0.8

                    # Promote if success rate is good
                    if success_rate >= 0.85:
                        await self.promote_model(model_info['model_name'], model_info['model_version'])
                        logger.info(f"🎉 Promoted {model_key} to active (success rate: {success_rate:.2f})")

                    elif success_rate < 0.7:
                        await self.deprecate_model(model_info['model_name'], model_info['model_version'])
                        logger.info(f"❌ Deprecated {model_key} (poor success rate: {success_rate:.2f})")

        except Exception as e:
            logger.error(f"❌ Error evaluating A/B tests: {e}")

    async def promote_model(self, model_name: str, version: str):
        """Promote a model from testing to active"""
        model_key = f"{model_name}_{version}"

        if model_key in self.model_versions:
            # Replace active model
            self.models[model_name] = self.model_versions[model_key]
            self.models[model_name]['status'] = 'active'

            # Save as active model file
            active_model_path = f"{model_name}.pkl"
            active_scaler_path = f"{model_name.replace('_model', '_scaler')}.pkl"

            joblib.dump(self.models[model_name]['model'], active_model_path)
            joblib.dump(self.models[model_name]['scaler'], active_scaler_path)

            # Update database
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE model_deployments
                SET deployment_type = 'full', deployment_percentage = 100, status = 'active'
                WHERE model_name = %s AND model_version = %s
            """, (model_name, version))
            self.conn.commit()

    async def deprecate_model(self, model_name: str, version: str):
        """Deprecate a poorly performing model"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE model_deployments
            SET status = 'deprecated', deprecated_at = NOW()
            WHERE model_name = %s AND model_version = %s
        """, (model_name, version))
        self.conn.commit()

# Main entry point for testing
async def main():
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'aether',
        'user': 'aether',
        'password': 'aether'
    }

    pipeline = TrainingPipeline(db_config)
    await pipeline.start_pipeline()

if __name__ == "__main__":
    asyncio.run(main())