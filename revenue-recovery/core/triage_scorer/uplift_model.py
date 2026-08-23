"""
Two-Model Causal Uplift Estimator (T-Learner).

Estimates the Conditional Average Treatment Effect (CATE):
    τ(x) = E[Y | X=x, T=1] - E[Y | X=x, T=0] = μ_1(x) - μ_0(x)

- μ_1(x) (model_treated): Trained on treated transactions (is_treated=True)
- μ_0(x) (model_control): Trained on untreated transactions (is_treated=False)
"""
import os
from pathlib import Path
from typing import Dict, Any, Union, Tuple, Optional, List
import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, accuracy_score

from simulator.generator import generate_batch
from core.triage_scorer.features import extract_features, extract_feature_matrix
from api.models.transaction import TransactionRecord

MODEL_DIR = Path(__file__).resolve().parent / "models"
TREATED_MODEL_PATH = MODEL_DIR / "uplift_treated.pkl"
CONTROL_MODEL_PATH = MODEL_DIR / "uplift_control.pkl"

_cached_treated_model: Optional[GradientBoostingClassifier] = None
_cached_control_model: Optional[GradientBoostingClassifier] = None


def train_uplift_models(n_samples: int = 12000, test_size: float = 0.20, random_state: int = 42) -> Tuple[GradientBoostingClassifier, GradientBoostingClassifier, Dict[str, Any]]:
    """
    Splits the synthetic dataset into treated and control subsets, trains two independent
    GradientBoostingClassifiers (μ_1 and μ_0), and evaluates them on held-out test splits.
    """
    print(f"Generating synthetic dataset (N={n_samples}) for Uplift T-Learner training...")
    records = generate_batch(n=n_samples)

    treated_records = [r for r in records if r["is_treated"]]
    control_records = [r for r in records if not r["is_treated"]]

    print(f"Dataset split: {len(treated_records)} Treated rows | {len(control_records)} Control rows")

    # 1. Train Treated Model (μ_1)
    X_treated = extract_feature_matrix(treated_records)
    y_treated = np.array([1 if r["actually_resolved"] else 0 for r in treated_records], dtype=np.int32)
    X_tr_train, X_tr_test, y_tr_train, y_tr_test = train_test_split(
        X_treated, y_treated, test_size=test_size, random_state=random_state, stratify=y_treated
    )

    model_treated = GradientBoostingClassifier(
        n_estimators=100,
        learning_rate=0.08,
        max_depth=4,
        random_state=random_state
    )
    model_treated.fit(X_tr_train, y_tr_train)
    auc_tr = roc_auc_score(y_tr_test, model_treated.predict_proba(X_tr_test)[:, 1])

    # 2. Train Control Model (μ_0)
    X_control = extract_feature_matrix(control_records)
    y_control = np.array([1 if r["actually_resolved"] else 0 for r in control_records], dtype=np.int32)
    X_co_train, X_co_test, y_co_train, y_co_test = train_test_split(
        X_control, y_control, test_size=test_size, random_state=random_state, stratify=y_control
    )

    model_control = GradientBoostingClassifier(
        n_estimators=100,
        learning_rate=0.08,
        max_depth=4,
        random_state=random_state
    )
    model_control.fit(X_co_train, y_co_train)
    auc_co = roc_auc_score(y_co_test, model_control.predict_proba(X_co_test)[:, 1])

    # Serialize both models
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model_treated, TREATED_MODEL_PATH)
    joblib.dump(model_control, CONTROL_MODEL_PATH)

    global _cached_treated_model, _cached_control_model
    _cached_treated_model = model_treated
    _cached_control_model = model_control

    metrics = {
        "treated_samples": len(treated_records),
        "control_samples": len(control_records),
        "treated_test_auc": round(float(auc_tr), 4),
        "control_test_auc": round(float(auc_co), 4),
    }
    print(f"✅ Serialized μ_1 -> {TREATED_MODEL_PATH} (Test AUC: {auc_tr:.4f})")
    print(f"✅ Serialized μ_0 -> {CONTROL_MODEL_PATH} (Test AUC: {auc_co:.4f})")

    return model_treated, model_control, metrics


def load_uplift_models() -> Tuple[GradientBoostingClassifier, GradientBoostingClassifier]:
    """
    Loads both serialized T-Learner models (μ_1 and μ_0).
    """
    global _cached_treated_model, _cached_control_model
    if _cached_treated_model is not None and _cached_control_model is not None:
        return _cached_treated_model, _cached_control_model

    if not TREATED_MODEL_PATH.exists() or not CONTROL_MODEL_PATH.exists():
        model_tr, model_co, _ = train_uplift_models()
        return model_tr, model_co

    _cached_treated_model = joblib.load(TREATED_MODEL_PATH)
    _cached_control_model = joblib.load(CONTROL_MODEL_PATH)
    return _cached_treated_model, _cached_control_model


def cate(feature_vector: np.ndarray) -> Union[float, np.ndarray]:
    """
    Computes estimated Conditional Average Treatment Effect (CATE):
        τ(x) = μ_1(x) - μ_0(x)
    """
    model_tr, model_co = load_uplift_models()
    
    if feature_vector.ndim == 1:
        X = feature_vector.reshape(1, -1)
        p1 = model_tr.predict_proba(X)[0, 1]
        p0 = model_co.predict_proba(X)[0, 1]
        return float(p1 - p0)
    else:
        p1 = model_tr.predict_proba(feature_vector)[:, 1]
        p0 = model_co.predict_proba(feature_vector)[:, 1]
        return p1 - p0


def estimate_cate_for_transaction(record: Union[Dict[str, Any], TransactionRecord]) -> float:
    """
    Inference helper: Computes CATE τ(x) for a given transaction record.
    """
    features = extract_features(record)
    tau = cate(features)
    return round(float(tau), 4)


if __name__ == "__main__":
    train_uplift_models()
