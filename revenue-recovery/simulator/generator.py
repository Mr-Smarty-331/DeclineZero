"""
Synthetic Transaction Generator for AI Revenue Recovery.

Generates realistic payment failures across checkout, subscription, and receivable categories,
sampling strictly from verified NPCI/Razorpay decline codes.

Phase 1b additions:
- Randomized Treatment/Control assignment (`is_treated`)
- Hidden Ground-Truth parameters (`gt_would_self_resolve`, `gt_nudge_effectiveness`, `gt_sleeping_dog`)
- Derived observable outcome (`actually_resolved`)
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
    ALL_VALID_CODES
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
    with explicit counterfactual ground-truth mechanisms for uplift modeling.
    """
    categories = list(CATEGORY_WEIGHTS.keys())
    weights = list(CATEGORY_WEIGHTS.values())
    category = random.choices(categories, weights=weights, k=1)[0]

    # ASSUMPTION: Peak transaction hours are 10:00 to 22:00 IST
    hour_weights = [1 if 0 <= h < 8 else 3 if 8 <= h < 12 else 4 if 12 <= h < 20 else 2 for h in range(24)]
    hour_of_day = random.choices(range(24), weights=hour_weights, k=1)[0]

    if category == "checkout":
        methods = list(CHECKOUT_METHOD_WEIGHTS.keys())
        method_weights = list(CHECKOUT_METHOD_WEIGHTS.values())
        payment_method = random.choices(methods, weights=method_weights, k=1)[0]
        # ASSUMPTION: Checkout ticket size log-normally distributed between INR 99 and INR 15,000
        amount = round(random.uniform(99.0, 15000.0), 2)
        decline_code = _sample_weighted(UPI_DECLINE_DISTRIBUTION)

    elif category == "subscription":
        payment_method = random.choice(["card", "upi_mandate"])
        # ASSUMPTION: Recurring subscription ticket size between INR 299 and INR 4,999
        amount = round(random.choice([299.0, 499.0, 999.0, 1499.0, 2499.0, 4999.0]), 2)
        decline_code = _sample_weighted(SUBSCRIPTION_DECLINE_DISTRIBUTION)

    else:  # receivable
        payment_method = "bank_transfer"
        # ASSUMPTION: B2B invoice ticket size between INR 5,000 and INR 250,000
        amount = round(random.uniform(5000.0, 250000.0), 2)
        decline_code = _sample_weighted(RECEIVABLE_DECLINE_DISTRIBUTION)

    # Sanity check: ensure sampled decline code belongs strictly to verified set
    assert decline_code in ALL_VALID_CODES, f"Invalid decline code generated: {decline_code}"

    # ------------------------------------------------------------------------------------------
    # PHASE 1b: COUNTERFACTUAL & UPLIFT GROUND-TRUTH CAUSAL DERIVATION
    # ------------------------------------------------------------------------------------------
    
    # ASSUMPTION: 50% randomized A/B treatment split across synthetic transactions
    is_treated = random.random() < 0.50

    # ASSUMPTION: Baseline self-resolution probability (without any proactive contact) varies by category & amount:
    # - Small checkout tickets (< INR 500) and timing issues (U69) have high self-resolution (~35%).
    # - High ticket receivables and insufficient funds (Z9) have low self-resolution (~5-10%).
    # - Risk-flagged codes never self-resolve without intervention (0%).
    if decline_code in ("U16", "34", "59", "K1", "S1", "S2", "S3"):
        self_resolve_prob = 0.0
    elif category == "checkout":
        self_resolve_prob = 0.35 if amount < 500 else 0.20 if amount < 2500 else 0.10
        if decline_code == "U69":
            self_resolve_prob += 0.10  # Customers who just timed out often retry on their own
    elif category == "subscription":
        self_resolve_prob = 0.15 if decline_code == "mandate_paused" else 0.05
    else:  # receivable
        self_resolve_prob = 0.08 if amount < 20000 else 0.03

    gt_would_self_resolve = random.random() < self_resolve_prob

    # ASSUMPTION: Nudge effectiveness (probability that reaching out successfully recovers the revenue when the customer
    # would NOT have self-resolved on their own):
    # - U69 (timing): High response to urgent payment link (~65%)
    # - U28 (bank technical): Moderate response to alternate method link (~55%)
    # - Z9 (insufficient funds): Moderate response when scheduled (~45%)
    # - Mandate lapsed: ~40%
    # - Receivables: ~35%
    # - Risk-flagged: 0% automated recovery (must be escalated)
    if decline_code in ("U16", "34", "59", "K1", "S1", "S2", "S3"):
        gt_nudge_effectiveness = 0.0
    elif decline_code == "U69":
        gt_nudge_effectiveness = 0.65
    elif decline_code == "U28":
        gt_nudge_effectiveness = 0.55
    elif decline_code == "Z9":
        gt_nudge_effectiveness = 0.45
    elif category == "subscription":
        gt_nudge_effectiveness = 0.40
    else:  # receivable
        gt_nudge_effectiveness = 0.35

    # ASSUMPTION: ~3% of high-amount checkout transactions are "sleeping dogs" where outreach triggers annoyance
    # or dispute rather than recovery.
    gt_sleeping_dog = (category == "checkout" and amount > 8000 and random.random() < 0.08)

    # ------------------------------------------------------------------------------------------
    # CAUSAL MECHANISM OUTCOME DERIVATION:
    # 1. If customer is a "sleeping dog" and was treated -> outreach causes negative effect (resolved = False).
    # 2. If gt_would_self_resolve is True -> customer completes payment regardless of treatment (resolved = True).
    # 3. If gt_would_self_resolve is False -> customer only resolves IF treated AND nudge roll succeeds.
    # ------------------------------------------------------------------------------------------
    if gt_sleeping_dog and is_treated:
        actually_resolved = False
    elif gt_would_self_resolve:
        actually_resolved = True
    elif is_treated and (random.random() < gt_nudge_effectiveness):
        actually_resolved = True
    else:
        actually_resolved = False

    return {
        # Core Phase 1a fields (Unchanged)
        "transaction_id": str(uuid.uuid4()),
        "category": category,
        "amount": amount,
        "hour_of_day": hour_of_day,
        "payment_method": payment_method,
        "decline_code": decline_code,
        
        # Phase 1b observable treatment field
        "is_treated": is_treated,
        "actually_resolved": actually_resolved,
        
        # Phase 1b hidden ground truth fields (prefixed with gt_)
        "gt_would_self_resolve": gt_would_self_resolve,
        "gt_nudge_effectiveness": gt_nudge_effectiveness,
        "gt_sleeping_dog": gt_sleeping_dog
    }


def generate_batch(n: int = 10000, output_path: Optional[str | Path] = None) -> List[Dict[str, Any]]:
    """
    Generates n transactions and saves them to a CSV file with full counterfactual ground truth.
    
    Why CSV format:
    - Zero external C-library binary reader dependencies.
    - Transparent, human-auditable, and natively parseable with Python's standard csv module and pandas.
    - Pathing is dynamically resolved relative to the simulator directory for portability.
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
        "is_treated",
        "actually_resolved",
        "gt_would_self_resolve",
        "gt_nudge_effectiveness",
        "gt_sleeping_dog"
    ]
    with open(target_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    return records
