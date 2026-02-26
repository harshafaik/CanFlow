import os
import joblib
import pandas as pd
import xgboost as xgb
import matplotlib.pyplot as plt
from datetime import datetime
from dotenv import load_dotenv
import clickhouse_connect
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.preprocessing import LabelEncoder

# Load environment variables
load_dotenv()

def get_clickhouse_client():
    return clickhouse_connect.get_client(
        host=os.getenv('CLICKHOUSE_HOST', 'localhost'),
        port=int(os.getenv('CLICKHOUSE_PORT', 8124)),
        username=os.getenv('CLICKHOUSE_USER', 'admin'),
        password=os.getenv('CLICKHOUSE_PASSWORD', 'password'),
        database=os.getenv('CLICKHOUSE_DATABASE', 'canflow')
    )

def main():
    client = get_clickhouse_client()
    
    print("1. Loading data from Gold layer...")
    query = "SELECT * FROM gold_vehicle_health"
    df = client.query_df(query)
    
    if df.empty:
        print("No data found in gold_vehicle_health. Exiting.")
        return

    print(f"Loaded {len(df)} vehicles.")

    print("2. Preparing features and target...")
    # Target: binary label — FAIR+POOR = 1 (At Risk), EXCELLENT+GOOD = 0 (Healthy)
    df['is_at_risk'] = df['health_score'].apply(lambda x: 1 if x < 70 else 0)

    # REFACTORED FEATURES: Remove the leaking averages and hard triggers
    # Use ONLY latent indicators that aren't directly in the SQL penalty logic
    df['maf_rpm_ratio'] = df['avg_maf'] / (df['avg_rpm'] + 1)
    df['volt_volatility'] = df['avg_battery_voltage'] - df['min_battery_voltage']
    
    features = [
        'maf_rpm_ratio', 'volt_volatility', 'max_coolant_temp_delta', 
        'vehicle_class'
    ]
    
    X = df[features].copy()
    y = df['is_at_risk']

    # Encode categorical feature
    le = LabelEncoder()
    X['vehicle_class'] = le.fit_transform(X['vehicle_class'])

    print("3. Training XGBoost...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    # Handle class imbalance
    negative_cases = (y_train == 0).sum()
    positive_cases = (y_train == 1).sum()
    scale_pos_weight = negative_cases / positive_cases if positive_cases > 0 else 1
    
    print(f"Class distribution: Healthy={negative_cases}, At-Risk={positive_cases}")
    print(f"Calculated scale_pos_weight: {scale_pos_weight:.2f}")

    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        scale_pos_weight=scale_pos_weight,
        use_label_encoder=False,
        eval_metric='logloss',
        random_state=42
    )

    model.fit(X_train, y_train)

    print("\nPlotting feature importance...")
    plt.figure(figsize=(10, 6))
    xgb.plot_importance(model)
    plt.title("Feature Importance - Vehicle Risk Model")
    plt.tight_layout()
    plt.savefig('models/feature_importance.png')
    print("Feature importance plot saved to models/feature_importance.png")

    # Evaluation
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    
    print("\nEvaluation Results:")
    print(classification_report(y_test, y_pred))
    print(f"AUC-ROC Score: {roc_auc_score(y_test, y_prob):.4f}")

    print("\n4. Saving the model...")
    os.makedirs('models', exist_ok=True)
    model_path = 'models/vehicle_risk_model.joblib'
    joblib.dump(model, model_path)
    # Also save the label encoder to ensure consistent inference
    joblib.dump(le, 'models/vehicle_class_encoder.joblib')
    print(f"Model saved to {model_path}")

    print("5. Writing predictions back to ClickHouse...")
    # Predict for the entire fleet
    all_probs = model.predict_proba(X)[:, 1]
    all_labels = model.predict(X)

    predictions_df = pd.DataFrame({
        'vehicle_id': df['vehicle_id'],
        'risk_probability': all_probs,
        'risk_label': all_labels.astype(int),
        'predicted_at': datetime.now()
    })

    # Ensure table exists
    client.command("""
        CREATE TABLE IF NOT EXISTS gold_vehicle_predictions (
            vehicle_id String,
            risk_probability Float64,
            risk_label UInt8,
            predicted_at DateTime
        ) ENGINE = MergeTree()
        ORDER BY predicted_at
    """)

    # Truncate to keep only latest batch (or keep all, depending on needs)
    client.command("TRUNCATE TABLE gold_vehicle_predictions")
    
    client.insert_df('gold_vehicle_predictions', predictions_df)
    print("Predictions successfully written to ClickHouse table: gold_vehicle_predictions")

if __name__ == "__main__":
    main()
