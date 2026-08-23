"""
Triage Decision Policy Engine for AI Revenue Recovery.

Applies causal decision rules combining baseline recoverability and estimated uplift:
1. DO_NOT_DISTURB: CATE τ(x) < 0 (Nudging customer causes negative impact / churn).
2. PASSIVE_HOLD: CATE τ(x) >= 0 and control resolution probability μ_0(x) >= 0.25 (Natural self-resolver).
3. DISPATCH: CATE τ(x) >= 0 and μ_0(x) < 0.25 (Persuadable recovery candidate needing outreach).
"""
from typing import Dict, Any, Union
import numpy as np

from api.models.transaction import TransactionRecord
from core.triage_scorer.features import extract_features
from core.triage_scorer.baseline_model import score_transaction
from core.triage_scorer.uplift_model import load_uplift_models, cate

# ASSUMPTION: Baseline self-resolution probability threshold identifying high-affinity self-resolvers
SELF_RESOLVE_THRESHOLD = 0.25


def triage_decision(record: Union[Dict[str, Any], TransactionRecord]) -> Dict[str, Any]:
    """
    Evaluates a transaction through the baseline model and uplift T-Learner,
    returning priority_score, cate_score, and routing decision.
    """
    model_tr, model_co = load_uplift_models()
    features = extract_features(record)
    X = features.reshape(1, -1)

    # 1. Baseline model recoverability score
    priority_score = score_transaction(record)

    # 2. Uplift T-Learner CATE score τ(x) and control baseline μ_0(x)
    p1 = float(model_tr.predict_proba(X)[0, 1])
    p0 = float(model_co.predict_proba(X)[0, 1])
    cate_score = round(p1 - p0, 4)

    # 3. Policy routing logic
    if cate_score < 0:
        decision = "DO_NOT_DISTURB"
    elif p0 >= SELF_RESOLVE_THRESHOLD:
        decision = "PASSIVE_HOLD"
    else:
        decision = "DISPATCH"

    return {
        "priority_score": round(priority_score, 4),
        "cate_score": cate_score,
        "decision": decision,
        "p0_baseline": round(p0, 4),
        "p1_treated": round(p1, 4)
    }
