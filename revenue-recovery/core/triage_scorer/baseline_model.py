"""
Baseline Triage Priority Classifier.

Trains a GradientBoostingClassifier to predict transaction recoverability probability (priority score)
from engineered transaction telemetry features.
"""
import os
from pathlib import Path
from typing import Dict, Any, Union, Tuple, Optional
import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, accuracy_score

from simulator.generator import generate_batch
from core.triage_scorer.features import extract_feature_matrix, extract_features
from api.models.transaction import TransactionRecord

MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_PATH = MODEL_DIR / "baseline_triage_model.pkl"

_cached_model: Optional[GradientBoostingClassifier] = None


def train_baseline_model(n_samples: int = 10000, test_size: float = 0.20, random_state: int = 42) -> Tuple[GradientBoostingClassifier, Dict[str, float]]:
    """
    Trains and serializes the baseline GradientBoostingClassifier triage model.
    Evaluates strictly on held-out test split.
    """
    print(f"Generating synthetic dataset (N={n_samples}) for baseline triage training...")
    records = generate_batch(n=n_samples)

    X = extract_feature_matrix(records)
    y = np.array([1 if r["actually_resolved"] else 0 for r in records], dtype=np.int32)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    print(f"Training GradientBoostingClassifier on {len(X_train)} samples...")
    model = GradientBoostingClassifier(
        n_estimators=100,
        learning_rate=0.08,
        max_depth=4,
        random_state=random_state
    )
    model.fit(X_train, y_train)

    # Evaluate on held-out test set
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_pred_proba >= 0.50).astype(int)

    auc = float(roc_auc_score(y_test, y_pred_proba))
    acc = float(accuracy_score(y_test, y_pred))

    metrics = {
        "test_roc_auc": round(auc, 4),
        "test_accuracy": round(acc, 4),
        "train_samples": len(X_train),
        "test_samples": len(X_test)
    }

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"✅ Baseline model serialized to: {MODEL_PATH}")
    print(f"   Held-out Test ROC-AUC: {auc:.4f} | Test Accuracy: {acc:.4f}")

    global _cached_model
    _cached_model = model

    return model, metrics


def load_baseline_model() -> GradientBoostingClassifier:
    """
    Loads serialized baseline model, or trains one if not yet present.
    """
    global _cached_model
    if _cached_model is not None:
        return _cached_model

    if not MODEL_PATH.exists():
        model, _ = train_baseline_model()
        return model

    _cached_model = joblib.load(MODEL_PATH)
    return _cached_model


def score_transaction(record: Union[Dict[str, Any], TransactionRecord]) -> float:
    """
    Inference helper: Computes priority recoverability score (0.0 to 1.0) for a transaction.
    """
    model = load_baseline_model()
    features = extract_features(record).reshape(1, -1)
    priority_score = float(model.predict_proba(features)[0, 1])
    return round(priority_score, 4)


if __name__ == "__main__":
    train_baseline_model()
