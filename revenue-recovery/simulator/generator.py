"""
Synthetic Transaction Generator for AI Revenue Recovery.

Generates realistic payment failures across checkout, subscription, and receivable categories,
sampling strictly from verified NPCI/Razorpay decline codes with intentional ambiguous residuals.

Phases implemented:
- Phase 1a: Verified taxonomy + weighted generator
- Phase 1b: Treatment/Control A/B split + hidden causal ground truth
- Phase 1c: Ambiguous cooperative bank legacy code injection + hidden root cause
- Phase 3a: Historical customer past success rate feature
"""
import os
import csv
import uuid
import random
from pathlib import Path
from typing import Dict, Any, List, Optional

from simulator.decline_codes import (
    UPIDeclineCode,
    SubscriptionDeclineCode,
    ReceivableDeclineCode,
    RootCauseCategory,
    ALL_VALID_CODES,
    LEGACY_AMBIGUOUS_CODES
)

# Relative default data directory inside the simulator module
DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_OUTPUT_PATH = DEFAULT_DATA_DIR / "synthetic_transactions.csv"

# ASSUMPTION: 60% of volume is checkout payment failures, 25% subscriptions, 15% invoices/receivables
CATEGORY_WEIGHTS = {
    "checkout": 0.60,
    "subscription": 0.25,
    "receivable": 0.15
}

# ASSUMPTION: Payment methods distribution for checkout transactions (UPI dominant in India)
CHECKOUT_METHOD_WEIGHTS = {
    "upi": 0.75,
    "card": 0.20,
    "netbanking": 0.05
}

# ASSUMPTION: Relative frequency of UPI decline codes in realistic merchant traffic:
# - Timing (U69): 35% (customer forgot / expired prompt)
# - Insufficient funds (Z9): 40% (common failure mode)
# - Bank technical glitch (U28): 15% (intermittent rail issues)
# - Risk/Fraud flags (U16, 34, 59, K1, S1-S3): 10% combined
UPI_DECLINE_DISTRIBUTION = [
    (UPIDeclineCode.U69.value, 0.35),
    (UPIDeclineCode.Z9.value, 0.40),
    (UPIDeclineCode.U28.value, 0.15),
    (UPIDeclineCode.U16.value, 0.02),
    (UPIDeclineCode.CODE_34.value, 0.02),
    (UPIDeclineCode.CODE_59.value, 0.02),
    (UPIDeclineCode.K1.value, 0.01),
    (UPIDeclineCode.S1.value, 0.01),
    (UPIDeclineCode.S2.value, 0.01),
    (UPIDeclineCode.S3.value, 0.01),
]

# ASSUMPTION: Subscription failures are 70% expired mandates, 30% paused mandates
SUBSCRIPTION_DECLINE_DISTRIBUTION = [
    (SubscriptionDeclineCode.MANDATE_EXPIRED.value, 0.70),
    (SubscriptionDeclineCode.MANDATE_PAUSED.value, 0.30),
]

# ASSUMPTION: Receivables are 80% undisputed overdue invoices, 20% disputed
RECEIVABLE_DECLINE_DISTRIBUTION = [
    (ReceivableDeclineCode.OVERDUE_NO_DISPUTE.value, 0.80),
    (ReceivableDeclineCode.OVERDUE_WITH_DISPUTE_FLAG.value, 0.20),
]


def _sample_weighted(distribution: List[tuple]) -> str:
    choices, weights = zip(*distribution)
    return random.choices(choices, weights=weights, k=1)[0]


def generate_transaction() -> Dict[str, Any]:
    """
    Generates a single synthetic payment failure record adhering strictly to the real taxonomy
    with explicit counterfactual ground-truth mechanisms, conformal residuals, and historical telemetry.
    """
    categories = list(CATEGORY_WEIGHTS.keys())
    weights = list(CATEGORY_WEIGHTS.values())
    category = random.choices(categories, weights=weights, k=1)[0]

    # ASSUMPTION: Peak transaction hours are 10:00 to 22:00 IST
    hour_weights = [1 if 0 <= h < 8 else 3 if 8 <= h < 12 else 4 if 12 <= h < 20 else 2 for h in range(24)]
    hour_of_day = random.choices(range(24), weights=hour_weights, k=1)[0]

    # ASSUMPTION: Customer past success rate is a legitimate merchant telemetry signal ranging between 0.30 and 0.99
    customer_past_success_rate = round(random.betavariate(5, 1.5) * 0.69 + 0.30, 3)

    # ------------------------------------------------------------------------------------------
    # PHASE 1c: AMBIGUOUS RESIDUAL INJECTION (~7% of traffic from unmapped cooperative banks)
    # ------------------------------------------------------------------------------------------
    is_ambiguous = (random.random() < 0.075)

    if is_ambiguous:
        decline_code = random.choice(LEGACY_AMBIGUOUS_CODES)
        gt_true_root_cause = random.choices(
            [
                RootCauseCategory.BANK_TECHNICAL_ISSUE.value,
                RootCauseCategory.TIMING_ATTENTION.value,
                RootCauseCategory.INSUFFICIENT_FUNDS.value,
                RootCauseCategory.RISK_FLAGGED.value,
            ],
            weights=[0.50, 0.25, 0.15, 0.10],
            k=1
        )[0]
    else:
        gt_true_root_cause = None

    if category == "checkout":
        methods = list(CHECKOUT_METHOD_WEIGHTS.keys())
        method_weights = list(CHECKOUT_METHOD_WEIGHTS.values())
        payment_method = random.choices(methods, weights=method_weights, k=1)[0]
        amount = round(random.uniform(99.0, 15000.0), 2)
        if not is_ambiguous:
            decline_code = _sample_weighted(UPI_DECLINE_DISTRIBUTION)

    elif category == "subscription":
        payment_method = random.choice(["card", "upi_mandate"])
        amount = round(random.choice([299.0, 499.0, 999.0, 1499.0, 2499.0, 4999.0]), 2)
        if not is_ambiguous:
            decline_code = _sample_weighted(SUBSCRIPTION_DECLINE_DISTRIBUTION)

    else:  # receivable
        payment_method = "bank_transfer"
        amount = round(random.uniform(5000.0, 250000.0), 2)
        if not is_ambiguous:
            decline_code = _sample_weighted(RECEIVABLE_DECLINE_DISTRIBUTION)

    if is_ambiguous:
        assert decline_code in LEGACY_AMBIGUOUS_CODES, f"Expected legacy code, got: {decline_code}"
    else:
        assert decline_code in ALL_VALID_CODES, f"Invalid decline code generated: {decline_code}"

    # ------------------------------------------------------------------------------------------
    # PHASE 1b: COUNTERFACTUAL & UPLIFT GROUND-TRUTH CAUSAL DERIVATION
    # ------------------------------------------------------------------------------------------
    is_treated = random.random() < 0.50

    effective_cause = gt_true_root_cause if is_ambiguous else decline_code

    if effective_cause in ("U16", "34", "59", "K1", "S1", "S2", "S3", RootCauseCategory.RISK_FLAGGED.value):
        self_resolve_prob = 0.0
    elif category == "checkout":
        self_resolve_prob = 0.35 if amount < 500 else 0.20 if amount < 2500 else 0.10
        if effective_cause in ("U69", RootCauseCategory.TIMING_ATTENTION.value):
            self_resolve_prob += 0.10
    elif category == "subscription":
        self_resolve_prob = 0.15 if effective_cause == "mandate_paused" else 0.05
    else:  # receivable
        self_resolve_prob = 0.08 if amount < 20000 else 0.03

    # Correlate baseline self-resolution slightly with customer's own historical reliability
    self_resolve_prob = min(0.95, self_resolve_prob * (customer_past_success_rate / 0.75))

    gt_would_self_resolve = random.random() < self_resolve_prob

    if effective_cause in ("U16", "34", "59", "K1", "S1", "S2", "S3", RootCauseCategory.RISK_FLAGGED.value):
        gt_nudge_effectiveness = 0.0
    elif effective_cause in ("U69", RootCauseCategory.TIMING_ATTENTION.value):
        gt_nudge_effectiveness = 0.65
    elif effective_cause in ("U28", RootCauseCategory.BANK_TECHNICAL_ISSUE.value):
        gt_nudge_effectiveness = 0.55
    elif effective_cause in ("Z9", RootCauseCategory.INSUFFICIENT_FUNDS.value):
        gt_nudge_effectiveness = 0.45
    elif category == "subscription":
        gt_nudge_effectiveness = 0.40
    else:  # receivable
        gt_nudge_effectiveness = 0.35

    gt_sleeping_dog = (category == "checkout" and amount > 8000 and random.random() < 0.08)

    if gt_sleeping_dog and is_treated:
        actually_resolved = False
    elif gt_would_self_resolve:
        actually_resolved = True
    elif is_treated and (random.random() < gt_nudge_effectiveness):
        actually_resolved = True
    else:
        actually_resolved = False

    return {
        # Core Phase 1a fields
        "transaction_id": str(uuid.uuid4()),
        "category": category,
        "amount": amount,
        "hour_of_day": hour_of_day,
        "payment_method": payment_method,
        "decline_code": decline_code,
        
        # Phase 3a historical signal
        "customer_past_success_rate": customer_past_success_rate,

        # Phase 1b observable & ground-truth fields
        "is_treated": is_treated,
        "actually_resolved": actually_resolved,
        "gt_would_self_resolve": gt_would_self_resolve,
        "gt_nudge_effectiveness": gt_nudge_effectiveness,
        "gt_sleeping_dog": gt_sleeping_dog,

        # Phase 1c ambiguous residual fields
        "is_ambiguous": is_ambiguous,
        "gt_true_root_cause": gt_true_root_cause
    }


def generate_batch(n: int = 10000, output_path: Optional[str | Path] = None) -> List[Dict[str, Any]]:
    """
    Generates n transactions and saves them to a CSV file with full counterfactual ground truth.
    """
    target_path = Path(output_path) if output_path else DEFAULT_OUTPUT_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    records = [generate_transaction() for _ in range(n)]

    fieldnames = [
        "transaction_id",
        "category",
        "amount",
        "hour_of_day",
        "payment_method",
        "decline_code",
        "customer_past_success_rate",
        "is_treated",
        "actually_resolved",
        "is_ambiguous",
        "gt_would_self_resolve",
        "gt_nudge_effectiveness",
        "gt_sleeping_dog",
        "gt_true_root_cause"
    ]
    with open(target_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    return records
