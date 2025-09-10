# aether/apps/ai-core/train.py

import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
import joblib

def train_model():
    """Loads the comprehensive dataset and trains the new model."""
    df = pd.read_csv('training_data.csv')

    # Use all the new features as input for the model
    X = df[[
        'gpu_temp', 
        'gpu_mem_used', 
        'job_type_training',
        'utilization_gpu',
        'power_draw_w',
        'throttling'
    ]]
    y = df['good_placement']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = xgb.XGBClassifier(objective='binary:logistic', eval_metric='logloss', use_label_encoder=False)
    model.fit(X_train, y_train)

    joblib.dump(model, 'scheduler_model.pkl')
    print("New, smarter model trained and saved to scheduler_model.pkl")

if __name__ == "__main__":
    train_model()
