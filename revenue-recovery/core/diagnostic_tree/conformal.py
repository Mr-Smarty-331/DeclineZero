"""
Conformal Prediction Engine for Ambiguous Legacy Residuals.

Constructs distribution-free uncertainty sets for unmapped cooperative bank error strings:
- Candidate Cause Space: Real taxonomy root causes from Phase 4a.
- Nonconformity Scorer: LAC score s(x, y) = 1 - P(Y=y | x).
- Split-Conformal Calibration: Computed on a dedicated held-out calibration split.
- Conformal Prediction Set Constructor: Γ(x) at error rate α (e.g. α=0.01 for 99% coverage).
- Abstention / Escalation: Abstains to AMBIGUOUS_ESCALATED whenever |Γ(x)| != 1.
"""
import os
import math
from pathlib import Path
from typing import Dict, Any, List, Tuple, Union, Optional
import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split

from simulator.generator import generate_batch
from simulator.decline_codes import LEGACY_AMBIGUOUS_CODES
from api.models.transaction import TransactionRecord

MODEL_DIR = Path(__file__).resolve().parent / "models"
BASE_MODEL_PATH = MODEL_DIR / "conformal_base_model.pkl"
CALIB_SCORES_PATH = MODEL_DIR / "conformal_calibration_scores.npy"

# Candidate root cause space (identical to Phase 4a taxonomy categories)
CANDIDATE_CAUSES = [
    "BANK_TECHNICAL_ISSUE",
    "INSUFFICIENT_FUNDS",
    "MANDATE_LAPSED",
    "OVERDUE_INVOICE",
    "RISK_FLAGGED",
    "TIMING_ATTENTION",
]
CAUSE_TO_IDX = {cause: i for i, cause in enumerate(CANDIDATE_CAUSES)}
IDX_TO_CAUSE = {i: cause for i, cause in enumerate(CANDIDATE_CAUSES)}

CAUSE_TO_ACTION = {
    "TIMING_ATTENTION": "SEND_FRESH_PAYMENT_LINK_URGENT",
    "INSUFFICIENT_FUNDS": "SCHEDULE_SALARY_ALIGNED_RETRY",
    "BANK_TECHNICAL_ISSUE": "SUGGEST_ALTERNATE_METHOD",
    "RISK_FLAGGED": "ESCALATE_HUMAN_REVIEW",
    "MANDATE_LAPSED": "SEND_MANDATE_REVIVAL_LINK",
    "OVERDUE_INVOICE": "SEND_REMINDER_TRACK_PROMISE",
}

_cached_base_model: Optional[GradientBoostingClassifier] = None
_cached_calib_scores: Optional[np.ndarray] = None


def extract_conformal_features(record: Union[Dict[str, Any], TransactionRecord]) -> np.ndarray:
    """
    Extracts features for ambiguous error diagnosis:
    - Monetary attributes: log(1+amount), micro/high ticket
    - Temporal telemetry: sin/cos cyclical hour
    - Customer history: customer_past_success_rate
    - Category & payment rail one-hots
    - Legacy error string pattern one-hots (ERR-BNK-0001 through ERR-BNK-0010)
    """
    if isinstance(record, TransactionRecord):
        data = record.model_dump()
    else:
        data = record

    amount = float(data.get("amount", 100.0))
    hour = int(data.get("hour_of_day", 12))
    past_success = float(data.get("customer_past_success_rate", 0.80))
    category = str(data.get("category", "checkout")).lower()
    method = str(data.get("payment_method", "upi")).lower()
    code = str(data.get("decline_code", "")).strip().upper()

    amount_log = math.log1p(max(0.0, amount))
    is_micro_ticket = 1.0 if amount < 500.0 else 0.0
    is_high_ticket = 1.0 if amount > 8000.0 else 0.0

    hour_sin = math.sin(2.0 * math.pi * hour / 24.0)
    hour_cos = math.cos(2.0 * math.pi * hour / 24.0)

    is_cat_checkout = 1.0 if category == "checkout" else 0.0
    is_cat_subscription = 1.0 if category == "subscription" else 0.0
    is_cat_receivable = 1.0 if category == "receivable" else 0.0

    is_method_upi = 1.0 if method == "upi" else 0.0
    is_method_card = 1.0 if method == "card" else 0.0
    is_method_netbanking = 1.0 if method == "netbanking" else 0.0
    is_method_upi_mandate = 1.0 if method == "upi_mandate" else 0.0
    is_method_bank_transfer = 1.0 if method == "bank_transfer" else 0.0

    legacy_code_feats = [1.0 if code == legacy else 0.0 for legacy in LEGACY_AMBIGUOUS_CODES]

    features = [
        amount_log,
        is_micro_ticket,
        is_high_ticket,
        hour_sin,
        hour_cos,
        past_success,
        is_cat_checkout,
        is_cat_subscription,
        is_cat_receivable,
        is_method_upi,
        is_method_card,
        is_method_netbanking,
        is_method_upi_mandate,
        is_method_bank_transfer,
    ] + legacy_code_feats

    return np.array(features, dtype=np.float32)


def _get_full_probabilities(model: GradientBoostingClassifier, X: np.ndarray) -> np.ndarray:
    raw_probs = model.predict_proba(X)
    full_probs = np.zeros((len(X), len(CANDIDATE_CAUSES)), dtype=np.float32)
    for col_idx, class_val in enumerate(model.classes_):
        full_probs[:, class_val] = raw_probs[:, col_idx]
    return full_probs


def train_conformal_base_model(
    n_total_samples: int = 25000,
    random_state: int = 42
) -> Tuple[GradientBoostingClassifier, np.ndarray, Dict[str, Any]]:
    print(f"Generating synthetic stream (N={n_total_samples}) to harvest ambiguous records...")
    batch = generate_batch(n=n_total_samples)

    ambiguous_records = [
        r for r in batch if r.get("is_ambiguous") and r.get("gt_true_root_cause") in CAUSE_TO_IDX
    ]
    n_ambiguous = len(ambiguous_records)
    print(f"Harvested {n_ambiguous} ambiguous records for conformal calibration.")

    X = np.vstack([extract_conformal_features(r) for r in ambiguous_records])
    y = np.array([CAUSE_TO_IDX[r["gt_true_root_cause"]] for r in ambiguous_records], dtype=np.int32)

    X_train_cal, X_test, y_train_cal, y_test = train_test_split(
        X, y, test_size=0.20, random_state=random_state, stratify=y
    )
    X_train, X_calib, y_train, y_calib = train_test_split(
        X_train_cal, y_train_cal, test_size=0.25, random_state=random_state, stratify=y_train_cal
    )

    model = GradientBoostingClassifier(
        n_estimators=100,
        learning_rate=0.08,
        max_depth=4,
        random_state=random_state
    )
    model.fit(X_train, y_train)

    calib_probs = _get_full_probabilities(model, X_calib)
    true_label_probs = calib_probs[np.arange(len(y_calib)), y_calib]
    calib_nonconformity_scores = 1.0 - true_label_probs

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, BASE_MODEL_PATH)
    np.save(CALIB_SCORES_PATH, calib_nonconformity_scores)

    global _cached_base_model, _cached_calib_scores
    _cached_base_model = model
    _cached_calib_scores = calib_nonconformity_scores

    stats = {
        "train_size": len(X_train),
        "calib_size": len(X_calib),
        "test_size": len(X_test),
        "min_score": round(float(np.min(calib_nonconformity_scores)), 4),
        "max_score": round(float(np.max(calib_nonconformity_scores)), 4),
        "mean_score": round(float(np.mean(calib_nonconformity_scores)), 4),
        "median_score": round(float(np.median(calib_nonconformity_scores)), 4),
    }

    return model, calib_nonconformity_scores, stats


def load_conformal_model_and_scores() -> Tuple[GradientBoostingClassifier, np.ndarray]:
    global _cached_base_model, _cached_calib_scores
    if _cached_base_model is not None and _cached_calib_scores is not None:
        return _cached_base_model, _cached_calib_scores

    if not BASE_MODEL_PATH.exists() or not CALIB_SCORES_PATH.exists():
        model, scores, _ = train_conformal_base_model()
        return model, scores

    _cached_base_model = joblib.load(BASE_MODEL_PATH)
    _cached_calib_scores = np.load(CALIB_SCORES_PATH)
    return _cached_base_model, _cached_calib_scores


def conformal_diagnose(
    record: Union[Dict[str, Any], TransactionRecord],
    alpha: float = 0.01
) -> Dict[str, Any]:
    """
    Constructs the distribution-free conformal prediction set Γ(x) at significance level α (default 0.01 -> 99% coverage).
    
    Returns:
    - Singleton: {"status": "SINGLETON", "root_cause": cause, "action": action, "prediction_set": [cause], "q_hat": float}
    - Ambiguous: {"status": "AMBIGUOUS_ESCALATED", "root_cause": "AMBIGUOUS", "action": "ESCALATE_HUMAN_REVIEW", "prediction_set": [...], "q_hat": float}
    - Empty:     {"status": "AMBIGUOUS_ESCALATED", "root_cause": "UNRECOGNIZED_EMPTY_SET", "action": "ESCALATE_HUMAN_REVIEW", "prediction_set": [], "q_hat": float}
    """
    model, calib_scores = load_conformal_model_and_scores()
    n_cal = len(calib_scores)

    # Compute conformal quantile q_hat with finite-sample correction
    q_level = min(1.0, math.ceil((n_cal + 1) * (1.0 - alpha)) / n_cal)
    q_hat = float(np.quantile(calib_scores, q_level))

    feats = extract_conformal_features(record).reshape(1, -1)
    probs = _get_full_probabilities(model, feats)[0]

    # Build prediction set: Γ(x) = { y | s(x, y) <= q_hat } where s(x, y) = 1 - P(Y=y | x)
    prediction_set = []
    cause_scores = {}
    for idx, cause in enumerate(CANDIDATE_CAUSES):
        score_y = 1.0 - probs[idx]
        cause_scores[cause] = round(float(score_y), 4)
        if score_y <= q_hat:
            prediction_set.append(cause)

    # 1. Singleton Resolution
    if len(prediction_set) == 1:
        resolved_cause = prediction_set[0]
        return {
            "status": "SINGLETON",
            "root_cause": resolved_cause,
            "action": CAUSE_TO_ACTION.get(resolved_cause, "SUGGEST_ALTERNATE_METHOD"),
            "confidence": "conformal_singleton",
            "prediction_set": prediction_set,
            "q_hat": round(q_hat, 4),
            "cause_scores": cause_scores
        }

    # 2. Multi-Candidate or Empty Set -> Conformal Abstention
    elif len(prediction_set) > 1:
        return {
            "status": "AMBIGUOUS_ESCALATED",
            "root_cause": "AMBIGUOUS",
            "action": "ESCALATE_HUMAN_REVIEW",
            "confidence": "conformal_multi_candidate",
            "prediction_set": prediction_set,
            "q_hat": round(q_hat, 4),
            "cause_scores": cause_scores
        }
    else:  # Empty set
        return {
            "status": "AMBIGUOUS_ESCALATED",
            "root_cause": "UNRECOGNIZED_EMPTY_SET",
            "action": "ESCALATE_HUMAN_REVIEW",
            "confidence": "conformal_empty_set",
            "prediction_set": [],
            "q_hat": round(q_hat, 4),
            "cause_scores": cause_scores
        }


def predict_cause_probabilities(record: Union[Dict[str, Any], TransactionRecord]) -> Dict[str, float]:
    model, _ = load_conformal_model_and_scores()
    feats = extract_conformal_features(record).reshape(1, -1)
    full_probs = _get_full_probabilities(model, feats)[0]
    return {IDX_TO_CAUSE[i]: round(float(full_probs[i]), 4) for i in range(len(CANDIDATE_CAUSES))}


if __name__ == "__main__":
    train_conformal_base_model()
