"""
Feature Engineering Pipeline for Triage Priority & Uplift Models.

Transforms transaction attributes into standardized numerical feature vectors:
1. Monetary signals: log(1 + amount), is_micro_ticket (<500), is_high_ticket (>8000)
2. Cyclical trigonometric hour encoding: sin(2π*h/24), cos(2π*h/24)
3. Historical customer past success rate telemetry
4. One-hot category encodings
5. One-hot payment method encodings
6. One-hot decline code / error classification signals
"""
import math
import numpy as np
from typing import Dict, Any, Union
from api.models.transaction import TransactionRecord

FEATURE_NAMES = [
    "amount_log",
    "is_micro_ticket",
    "is_high_ticket",
    "hour_sin",
    "hour_cos",
    "customer_past_success_rate",
    # Category
    "is_cat_checkout",
    "is_cat_subscription",
    "is_cat_receivable",
    # Payment Method
    "is_method_upi",
    "is_method_card",
    "is_method_netbanking",
    "is_method_upi_mandate",
    "is_method_bank_transfer",
    # Decline Code Signals
    "is_code_u69",
    "is_code_z9",
    "is_code_u28",
    "is_code_risk",
    "is_code_mandate_expired",
    "is_code_mandate_paused",
    "is_code_overdue_no_dispute",
    "is_code_overdue_disputed",
    "is_code_ambiguous",
]


def extract_features(record: Union[Dict[str, Any], TransactionRecord]) -> np.ndarray:
    """
    Extracts a 1D numerical pre-treatment feature vector from a transaction dictionary or Pydantic record.
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
    code = str(data.get("decline_code", "")).upper()
    is_ambiguous = bool(data.get("is_ambiguous", False)) or code.startswith("ERR-BNK")

    # 1. Non-linear log & threshold monetary features
    amount_log = math.log1p(max(0.0, amount))
    is_micro_ticket = 1.0 if amount < 500.0 else 0.0
    is_high_ticket = 1.0 if amount > 8000.0 else 0.0

    # 2. Cyclical sin/cos encoding for 24-hour time representation
    hour_sin = math.sin(2.0 * math.pi * hour / 24.0)
    hour_cos = math.cos(2.0 * math.pi * hour / 24.0)

    # 3. Category one-hot encodings
    is_cat_checkout = 1.0 if category == "checkout" else 0.0
    is_cat_subscription = 1.0 if category == "subscription" else 0.0
    is_cat_receivable = 1.0 if category == "receivable" else 0.0

    # 4. Payment method one-hot encodings
    is_method_upi = 1.0 if method == "upi" else 0.0
    is_method_card = 1.0 if method == "card" else 0.0
    is_method_netbanking = 1.0 if method == "netbanking" else 0.0
    is_method_upi_mandate = 1.0 if method == "upi_mandate" else 0.0
    is_method_bank_transfer = 1.0 if method == "bank_transfer" else 0.0

    # 5. Decline code classification features
    is_code_u69 = 1.0 if code == "U69" else 0.0
    is_code_z9 = 1.0 if code == "Z9" else 0.0
    is_code_u28 = 1.0 if code == "U28" else 0.0
    is_code_risk = 1.0 if code in ("U16", "34", "59", "K1", "S1", "S2", "S3") else 0.0
    is_code_mandate_expired = 1.0 if "MANDATE_EXPIRED" in code else 0.0
    is_code_mandate_paused = 1.0 if "MANDATE_PAUSED" in code else 0.0
    is_code_overdue_no_dispute = 1.0 if code == "OVERDUE_NO_DISPUTE" else 0.0
    is_code_overdue_disputed = 1.0 if "DISPUTE" in code and code != "OVERDUE_NO_DISPUTE" else 0.0
    is_code_ambiguous_val = 1.0 if is_ambiguous else 0.0

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
        is_code_u69,
        is_code_z9,
        is_code_u28,
        is_code_risk,
        is_code_mandate_expired,
        is_code_mandate_paused,
        is_code_overdue_no_dispute,
        is_code_overdue_disputed,
        is_code_ambiguous_val,
    ]

    return np.array(features, dtype=np.float32)


def extract_feature_matrix(records: list) -> np.ndarray:
    """
    Extracts a 2D feature matrix (N, 23) from a list of records.
    """
    return np.vstack([extract_features(r) for r in records])
