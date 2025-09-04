import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
import joblib

def train_model():
    """Loads data, trains an XGBoost model, and saves it."""
    df = pd.read_csv('training_data.csv')

    X = df[['gpu_temp', 'gpu_mem_used', 'job_type_training']]
    y = df['good_placement']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = xgb.XGBClassifier(objective='binary:logistic', eval_metric='logloss', use_label_encoder=False)
    model.fit(X_train, y_train)

    # Save the trained model to a file
    joblib.dump(model, 'scheduler_model.pkl')
    print("Model trained and saved to scheduler_model.pkl")

if __name__ == "__main__":
    train_model()
