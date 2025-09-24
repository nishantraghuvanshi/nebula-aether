#!/usr/bin/env python3
"""
Enhanced Model Training Script

Trains multi-output neural network models for GPU scheduling using the enhanced training data.
Creates separate models for different job types and a general model.
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.metrics import mean_squared_error, r2_score
import joblib
import json
import os

class BackwardCompatibleModel:
    """Backward compatible model wrapper for existing API"""

    def __init__(self, multi_model, scaler, feature_columns):
        self.multi_model = multi_model
        self.scaler = scaler
        self.feature_columns = feature_columns

    def predict_proba(self, X):
        """Simulate predict_proba for compatibility"""
        # Scale features
        X_scaled = self.scaler.transform(X)

        # Get multi-output predictions
        predictions = self.multi_model.predict(X_scaled)

        # Extract performance scores (first column)
        performance_scores = predictions[:, 0]  # performance_score column

        # Convert to probability-like format (0-1 range)
        # Performance scores are 0-100, convert to 0-1
        probs = performance_scores / 100.0
        probs = np.clip(probs, 0.0, 1.0)  # Ensure 0-1 range

        # Create binary probability array format expected by existing code
        # Column 0: probability of "bad" placement (1 - performance)
        # Column 1: probability of "good" placement (performance)
        result = np.column_stack([1 - probs, probs])

        return result

    def predict(self, X):
        """Binary prediction for compatibility"""
        proba = self.predict_proba(X)
        return (proba[:, 1] > 0.5).astype(int)

class EnhancedModelTrainer:
    """Trains enhanced GPU scheduling models"""

    def __init__(self, data_file: str = 'enhanced_training_data.csv'):
        self.data_file = data_file
        self.models = {}
        self.scalers = {}
        self.feature_columns = []

    def load_and_prepare_data(self):
        """Load and prepare the enhanced training data"""

        print(f"Loading enhanced training data from {self.data_file}...")
        self.df = pd.read_csv(self.data_file)

        print(f"Loaded {len(self.df)} samples with {len(self.df.columns)} features")

        # Define feature columns (exclude target variables and metadata)
        excluded_columns = ['performance_score', 'thermal_risk', 'memory_risk', 'scenario_name', 'job_type']
        self.feature_columns = [col for col in self.df.columns if col not in excluded_columns]

        print(f"Using {len(self.feature_columns)} features for training:")
        for i, col in enumerate(self.feature_columns):
            print(f"  {i+1:2d}. {col}")

        # Define target columns
        self.target_columns = ['performance_score', 'thermal_risk', 'memory_risk']

        return self.df

    def prepare_features_targets(self, df_subset):
        """Prepare feature matrix and target variables"""

        X = df_subset[self.feature_columns].values
        y = df_subset[self.target_columns].values

        return X, y

    def train_model(self, X_train, y_train, model_name: str):
        """Train a multi-output random forest model"""

        print(f"\nTraining {model_name} model...")

        # Create and train scaler
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)

        # Create multi-output random forest model
        rf = RandomForestRegressor(
            n_estimators=100,
            max_depth=15,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        )

        model = MultiOutputRegressor(rf)
        model.fit(X_train_scaled, y_train)

        # Store model and scaler
        self.models[model_name] = model
        self.scalers[model_name] = scaler

        return model, scaler

    def evaluate_model(self, model, scaler, X_test, y_test, model_name: str):
        """Evaluate model performance"""

        X_test_scaled = scaler.transform(X_test)
        y_pred = model.predict(X_test_scaled)

        print(f"\n{model_name} Model Evaluation:")

        for i, target in enumerate(self.target_columns):
            mse = mean_squared_error(y_test[:, i], y_pred[:, i])
            r2 = r2_score(y_test[:, i], y_pred[:, i])

            print(f"  {target}:")
            print(f"    MSE: {mse:.4f}")
            print(f"    R²:  {r2:.4f}")

            # Additional statistics
            y_true_mean = np.mean(y_test[:, i])
            y_pred_mean = np.mean(y_pred[:, i])
            print(f"    True mean: {y_true_mean:.3f}, Pred mean: {y_pred_mean:.3f}")

    def train_job_specific_models(self):
        """Train separate models for each job type"""

        job_types = ['training', 'inference', 'compute', 'memory']

        for job_type in job_types:
            print(f"\n{'='*50}")
            print(f"Training {job_type.upper()} specific model")
            print(f"{'='*50}")

            # Filter data for this job type
            job_data = self.df[self.df[f'job_type_{job_type}'] == 1].copy()

            if len(job_data) < 100:
                print(f"Insufficient data for {job_type} model ({len(job_data)} samples). Skipping.")
                continue

            print(f"Using {len(job_data)} samples for {job_type} model")

            # Prepare data
            X, y = self.prepare_features_targets(job_data)

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

            # Train model
            model, scaler = self.train_model(X_train, y_train, job_type)

            # Evaluate model
            self.evaluate_model(model, scaler, X_test, y_test, job_type)

    def train_general_model(self):
        """Train a general model using all data"""

        print(f"\n{'='*50}")
        print(f"Training GENERAL model")
        print(f"{'='*50}")

        # Use all data
        X, y = self.prepare_features_targets(self.df)

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        print(f"Using {len(X_train)} training samples and {len(X_test)} test samples")

        # Train model
        model, scaler = self.train_model(X_train, y_train, 'general')

        # Evaluate model
        self.evaluate_model(model, scaler, X_test, y_test, 'general')

    def save_models(self):
        """Save all trained models"""

        print(f"\nSaving models...")

        for model_name, model in self.models.items():
            model_file = f'{model_name}_model.pkl'
            scaler_file = f'{model_name}_scaler.pkl'

            joblib.dump(model, model_file)
            joblib.dump(self.scalers[model_name], scaler_file)

            print(f"  Saved {model_name} model to {model_file}")
            print(f"  Saved {model_name} scaler to {scaler_file}")

        # Save feature information
        model_info = {
            'feature_columns': self.feature_columns,
            'target_columns': self.target_columns,
            'num_features': len(self.feature_columns),
            'num_targets': len(self.target_columns),
            'models_trained': list(self.models.keys()),
            'data_samples': len(self.df)
        }

        with open('model_info.json', 'w') as f:
            json.dump(model_info, f, indent=2)

        print(f"  Saved model info to model_info.json")

    def create_backward_compatible_model(self):
        """Create a backward compatible model for the existing API"""

        print(f"\nCreating backward compatible model...")

        # Use the general model to create a simplified version that outputs just performance score
        general_model = self.models.get('general')
        general_scaler = self.scalers.get('general')

        if general_model is None:
            print("General model not found. Cannot create backward compatible model.")
            return

        # Create backward compatible model
        compat_model = BackwardCompatibleModel(
            general_model, general_scaler, self.feature_columns
        )

        # Save as scheduler_model.pkl for compatibility
        joblib.dump(compat_model, 'scheduler_model.pkl')
        print("  Saved backward compatible model to scheduler_model.pkl")

    def train_all_models(self):
        """Train all models"""

        # Load data
        self.load_and_prepare_data()

        # Train general model
        self.train_general_model()

        # Train job-specific models
        self.train_job_specific_models()

        # Save all models
        self.save_models()

        # Create backward compatible model
        self.create_backward_compatible_model()

        print(f"\n{'='*60}")
        print("Enhanced model training complete!")
        print(f"{'='*60}")
        print("Models created:")
        for model_name in self.models.keys():
            print(f"  • {model_name}_model.pkl")
        print("  • scheduler_model.pkl (backward compatible)")

def main():
    """Main training function"""

    # Check if enhanced training data exists
    if not os.path.exists('enhanced_training_data.csv'):
        print("Enhanced training data not found. Please run generate_training_data.py first.")
        return

    # Create trainer and train models
    trainer = EnhancedModelTrainer()
    trainer.train_all_models()

if __name__ == "__main__":
    main()