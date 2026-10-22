import pandas as pd
import json
import joblib
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, classification_report
import numpy as np

BASE = Path(".")

df = pd.read_csv(BASE / "processed_all_songs.csv", low_memory=False)
print(f"Dataset: {len(df)} songs ({len(df[df['Target']==1])} liked, {len(df[df['Target']==0])} disliked)")

model = joblib.load(BASE / "model_tags_only.pkl")
with open(BASE / "feature_columns_tags_only.json") as f:
    feature_cols = json.load(f)

print(f"Features: {len(feature_cols)}")

X = df[feature_cols].fillna(0)
y = df['Target']

# Same split as training
plays = pd.to_numeric(df['Plays'], errors='coerce').fillna(0).clip(lower=0)
weights = np.log1p(plays) + 1
weights = weights / weights.mean()

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42, stratify=y)
y_pred = model.predict(X_test)

print(f"\nTest Accuracy: {accuracy_score(y_test, y_pred):.4f}")
print(f"Test F1: {f1_score(y_test, y_pred):.4f}")
print(f"\n{classification_report(y_test, y_pred, target_names=['Disliked', 'Liked'])}")
