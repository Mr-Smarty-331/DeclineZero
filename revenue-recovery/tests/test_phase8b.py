"""
Phase 8b Unit Test: Baseline Simulator Calculation & Compliance Spot-Checking.

Validates the simulation math on 5 hand-crafted test cases:
1. RISK_FLAGGED (U16): Blind retry causes 1 compliance violation; Rules-only ignores.
2. DO_NOT_DISTURB (gt_sleeping_dog=True): Blind retry & Rules-only cause 1 compliance violation + churn; Recovers ₹0.
3. Persuadable Normal (UPI U69, nudge=0.80): Recovers ₹1,500 across all active policies.
4. Night-Time Failure (Hour=23): Blind retry violates night contact rule; Rules-only halts.
5. Ineffective Attempt (nudge=0.10, self_resolve=False): Fails recovery across all active policies.
"""
from core.evaluator.baseline_comparator import (
    evaluate_blind_retry_policy,
    evaluate_rules_no_uplift_policy
)

def test_baseline_math_spot_check():
    print("\n============================================================")
    print("      RUNNING PHASE 8b BASELINE COMPARATOR UNIT TEST")
    print("============================================================")

    # 5 Hand-crafted transactions
    sample_txns = [
        # Case 1: Risk Flagged
        {
            "transaction_id": "spot_risk_01",
            "amount": 2000.0,
            "hour_of_day": 14,
            "decline_code": "U16",
            "gt_sleeping_dog": False,
            "gt_would_self_resolve": False,
            "gt_nudge_effectiveness": 0.0
        },
        # Case 2: Sleeping Dog (DO_NOT_DISTURB)
        {
            "transaction_id": "spot_dnd_02",
            "amount": 3500.0,
            "hour_of_day": 12,
            "decline_code": "generic_decline",
            "gt_sleeping_dog": True,
            "gt_would_self_resolve": True,  # Would have paid if left alone, but outreach churns them
            "gt_nudge_effectiveness": -0.40
        },
        # Case 3: Clean Persuadable Normal
        {
            "transaction_id": "spot_clean_03",
            "amount": 1500.0,
            "hour_of_day": 11,
            "decline_code": "U69",
            "gt_sleeping_dog": False,
            "gt_would_self_resolve": False,
            "gt_nudge_effectiveness": 0.80
        },
        # Case 4: Night Time Transaction (Hour 23)
        {
            "transaction_id": "spot_night_04",
            "amount": 4000.0,
            "hour_of_day": 23,
            "decline_code": "Z9",
            "gt_sleeping_dog": False,
            "gt_would_self_resolve": False,
            "gt_nudge_effectiveness": 0.70
        },
        # Case 5: Ineffective Attempt
        {
            "transaction_id": "spot_ineff_05",
            "amount": 1000.0,
            "hour_of_day": 16,
            "decline_code": "card_declined",
            "gt_sleeping_dog": False,
            "gt_would_self_resolve": False,
            "gt_nudge_effectiveness": 0.10
        }
    ]

    # --- Test 1: Blind Retry Policy Evaluation ---
    blind_res = evaluate_blind_retry_policy(sample_txns)
    print("\n--- Blind Retry Policy Spot Check (5 Cases) ---")
    print(f"  Recovered Amount   : ₹{blind_res['recovered_amount_inr']:.2f}")
    print(f"  Total Cost         : ₹{blind_res['total_outreach_cost_inr']:.2f} (5 x ₹0.50)")
    print(f"  Compliance Total   : {blind_res['compliance_violations']} violations")
    print(f"  - Risk Retries     : {blind_res['risk_auto_retries']}")
    print(f"  - Sleeping Churns  : {blind_res['customer_churn_incidents']}")
    print(f"  - Night Contacts   : {blind_res['night_contacts']}")

    # Expected by hand:
    # Net value = 1500 - 2.50 - 3500 (churn) - 15000 (3 violations x 5000) = -₹17,002.50
    assert blind_res["total_outreach_cost_inr"] == 2.50
    assert blind_res["risk_auto_retries"] == 1
    assert blind_res["customer_churn_incidents"] == 1
    assert blind_res["monetized_churn_cost_inr"] == 3500.00
    assert blind_res["regulatory_penalty_cost_inr"] == 15000.00
    assert blind_res["night_contacts"] == 1
    assert blind_res["compliance_violations"] == 3
    assert blind_res["net_recovered_inr"] == -17002.50
    print(f"  - Monetized Churn  : ₹{blind_res['monetized_churn_cost_inr']:.2f}")
    print(f"  - Reg. Penalty     : ₹{blind_res['regulatory_penalty_cost_inr']:.2f}")
    print(f"  - Net Value        : ₹{blind_res['net_recovered_inr']:.2f}")
    print("  [PASS] Blind retry manual math matches 100%.")

    # --- Test 2: Rules-Only (No Uplift) Policy Evaluation ---
    rules_res = evaluate_rules_no_uplift_policy(sample_txns)
    print("\n--- Rules-Only Policy Spot Check (5 Cases) ---")
    print(f"  Recovered Amount   : ₹{rules_res['recovered_amount_inr']:.2f}")
    print(f"  Total Cost         : ₹{rules_res['total_outreach_cost_inr']:.2f}")
    print(f"  Monetized Churn    : ₹{rules_res['monetized_churn_cost_inr']:.2f}")
    print(f"  Reg. Penalty       : ₹{rules_res['regulatory_penalty_cost_inr']:.2f}")
    print(f"  Net Value          : ₹{rules_res['net_recovered_inr']:.2f}")
    print(f"  Compliance Total   : {rules_res['compliance_violations']} violations")

    # Expected by hand:
    # Recovered = ₹1500.00
    # Total cost = 3 contacts x ₹0.50 = ₹1.50
    # Monetized churn = 1 x ₹3500 = ₹3500.00
    # Regulatory penalty = 1 x ₹5000 = ₹5000.00
    # Net value = 1500 - 1.50 - 3500 - 5000 = -₹7001.50
    assert rules_res["recovered_amount_inr"] == 1500.00
    assert rules_res["total_outreach_cost_inr"] == 1.50
    assert rules_res["monetized_churn_cost_inr"] == 3500.00
    assert rules_res["regulatory_penalty_cost_inr"] == 5000.00
    assert rules_res["net_recovered_inr"] == -7001.50
    assert rules_res["compliance_violations"] == 1
    assert rules_res["customer_churn_incidents"] == 1
    print("  [PASS] Rules-only manual math matches 100%.")

    print("\n🎉 ALL 5 SPOT-CHECK SCENARIOS MATHEMATICALLY VERIFIED!\n")

if __name__ == "__main__":
    test_baseline_math_spot_check()
