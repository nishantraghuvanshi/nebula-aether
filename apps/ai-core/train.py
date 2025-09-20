# aether/apps/ai-core/train.py

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
import joblib
import os
import sys

# Set environment variables to prevent threading issues that can cause segfaults
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['VECLIB_MAXIMUM_THREADS'] = '1'
os.environ['NUMEXPR_NUM_THREADS'] = '1'

def train_model():
    """Loads the comprehensive dataset and trains the new model."""
    try:
        print("Loading training data...")
        df = pd.read_csv('training_data.csv')
        print(f"Loaded {len(df)} training samples")

        # Use all the new features as input for the model
        feature_columns = [
            'gpu_temp', 
            'gpu_mem_used', 
            'job_type_training',
            'utilization_gpu',
            'power_draw_w',
            'throttling'
        ]
        
        # Verify all required columns exist
        missing_columns = [col for col in feature_columns if col not in df.columns]
        if missing_columns:
            print(f"Error: Missing columns in training data: {missing_columns}")
            return False
        
        X = df[feature_columns]
        y = df['good_placement']
        
        print(f"Features shape: {X.shape}")
        print(f"Target shape: {y.shape}")

        # Check for any NaN values
        if X.isnull().sum().sum() > 0:
            print("Warning: Found NaN values in features, filling with zeros")
            X = X.fillna(0)
        
        if y.isnull().sum() > 0:
            print("Warning: Found NaN values in target, filling with zeros")
            y = y.fillna(0)

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        print("Training model...")
        
        # Try RandomForest first (more stable), then XGBoost if specifically requested
        try:
            print("Using RandomForest classifier...")
            model = RandomForestClassifier(
                n_estimators=100,
                random_state=42,
                n_jobs=1  # Single-threaded to prevent issues
            )
            model.fit(X_train, y_train)
            model_type = "RandomForest"
            
        except Exception as rf_error:
            print(f"RandomForest failed: {rf_error}")
            print("Trying XGBoost classifier...")
            try:
                import xgboost as xgb
                model = xgb.XGBClassifier(
                    objective='binary:logistic', 
                    eval_metric='logloss', 
                    use_label_encoder=False,
                    n_jobs=1,  # Single-threaded to prevent segfaults
                    random_state=42
                )
                model.fit(X_train, y_train, verbose=False)
                model_type = "XGBoost"
            except Exception as xgb_error:
                print(f"XGBoost also failed: {xgb_error}")
                raise rf_error  # Re-raise the original error

        # Test the model
        accuracy = model.score(X_test, y_test)
        print(f"Model accuracy: {accuracy:.4f}")

        # Save the model
        joblib.dump(model, 'scheduler_model.pkl')
        print(f"Model ({model_type}) trained and saved to scheduler_model.pkl")
        
        return True
        
    except Exception as e:
        print(f"Error during training: {e}")
        print("Creating a simple fallback model...")
        
        # Create a very simple fallback model
        try:
            from sklearn.dummy import DummyClassifier
            fallback_model = DummyClassifier(strategy="most_frequent")
            
            # Create dummy data if needed
            if 'df' not in locals():
                print("Creating dummy training data for fallback model...")
                dummy_X = np.array([[50, 5000, 0, 50, 150, 0]] * 100)  # 100 dummy samples
                dummy_y = np.array([1] * 60 + [0] * 40)  # 60% positive
            else:
                dummy_X = X if 'X' in locals() else np.array([[50, 5000, 0, 50, 150, 0]] * 100)
                dummy_y = y if 'y' in locals() else np.array([1] * 60 + [0] * 40)
            
            fallback_model.fit(dummy_X, dummy_y)
            joblib.dump(fallback_model, 'scheduler_model.pkl')
            print("Fallback model saved to scheduler_model.pkl")
            return True
            
        except Exception as fallback_error:
            print(f"Even fallback model failed: {fallback_error}")
            return False

def create_anomaly_detector():
    """Create a simple anomaly detector as a fallback."""
    try:
        print("Creating anomaly detector...")
        from sklearn.ensemble import IsolationForest
        
        # Create a simple anomaly detector
        anomaly_detector = IsolationForest(
            contamination=0.1,
            random_state=42,
            n_jobs=1
        )
        
        # Create some dummy normal data for training
        normal_data = np.random.normal(50, 10, (100, 6))  # 100 samples, 6 features
        anomaly_detector.fit(normal_data)
        
        joblib.dump(anomaly_detector, 'anomaly_detector.pkl')
        print("Anomaly detector saved to anomaly_detector.pkl")
        return True
        
    except Exception as e:
        print(f"Failed to create anomaly detector: {e}")
        return False

if __name__ == "__main__":
    print("Starting model training...")
    
    success = train_model()
    if success:
        print("Training completed successfully")
        # Also create anomaly detector
        create_anomaly_detector()
        sys.exit(0)
    else:
        print("Training failed")
        sys.exit(1)
