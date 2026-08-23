"""
Phase 1c Part 2 Unit Test: Mock Razorpay Webhook Emitter Sample Payloads.

Validates:
1. Converting synthetic transactions to standard Razorpay webhook payloads.
2. Emits 5 distinct sample categories for visual structure inspection.
"""
import json
from simulator.webhook_emitter import transaction_to_razorpay_webhook

def test_sample_webhook_emissions():
    samples = [
        {
            "name": "1. Standard Normal Decline (Timing - U69)",
            "txn": {
                "transaction_id": "8a7b6c5d-4e3f-2a1b-0c9d-8e7f6a5b4c3d",
                "category": "checkout",
                "amount": 499.00,
                "hour_of_day": 14,
                "payment_method": "upi",
                "decline_code": "U69",
                "is_treated": True,
                "actually_resolved": True,
                "is_ambiguous": False,
                "gt_would_self_resolve": False,
                "gt_nudge_effectiveness": 0.65,
                "gt_sleeping_dog": False,
                "gt_true_root_cause": None
            }
        },
        {
            "name": "2. Risk-Flagged Decline (Security - U16)",
            "txn": {
                "transaction_id": "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
                "category": "checkout",
                "amount": 12500.00,
                "hour_of_day": 2,
                "payment_method": "card",
                "decline_code": "U16",
                "is_treated": False,
                "actually_resolved": False,
                "is_ambiguous": False,
                "gt_would_self_resolve": False,
                "gt_nudge_effectiveness": 0.0,
                "gt_sleeping_dog": False,
                "gt_true_root_cause": None
            }
        },
        {
            "name": "3. Ambiguous Legacy Residual (ERR-BNK-0004)",
            "txn": {
                "transaction_id": "9f8e7d6c-5b4a-3f2e-1d0c-9b8a7f6e5d4c",
                "category": "checkout",
                "amount": 1850.00,
                "hour_of_day": 17,
                "payment_method": "netbanking",
                "decline_code": "ERR-BNK-0004",
                "is_treated": True,
                "actually_resolved": False,
                "is_ambiguous": True,
                "gt_would_self_resolve": False,
                "gt_nudge_effectiveness": 0.55,
                "gt_sleeping_dog": False,
                "gt_true_root_cause": "BANK_TECHNICAL_ISSUE"
            }
        },
        {
            "name": "4. Subscription Mandate Lapsed (mandate_expired)",
            "txn": {
                "transaction_id": "3c2b1a0f-9e8d-7c6b-5a4f-3e2d1c0b9a8f",
                "category": "subscription",
                "amount": 999.00,
                "hour_of_day": 9,
                "payment_method": "card",
                "decline_code": "mandate_expired",
                "is_treated": True,
                "actually_resolved": True,
                "is_ambiguous": False,
                "gt_would_self_resolve": False,
                "gt_nudge_effectiveness": 0.40,
                "gt_sleeping_dog": False,
                "gt_true_root_cause": None
            }
        },
        {
            "name": "5. Receivable Overdue with Dispute (overdue_with_dispute_flag)",
            "txn": {
                "transaction_id": "7d6c5b4a-3f2e-1d0c-9b8a-7f6e5d4c3b2a",
                "category": "receivable",
                "amount": 45000.00,
                "hour_of_day": 11,
                "payment_method": "bank_transfer",
                "decline_code": "overdue_with_dispute_flag",
                "is_treated": False,
                "actually_resolved": False,
                "is_ambiguous": False,
                "gt_would_self_resolve": False,
                "gt_nudge_effectiveness": 0.35,
                "gt_sleeping_dog": False,
                "gt_true_root_cause": None
            }
        }
    ]

    print("\n======================================================================")
    print("        PHASE 1c PART 2: 5 SAMPLE RAZORPAY WEBHOOK PAYLOADS")
    print("======================================================================\n")

    for item in samples:
        print(f"--- SAMPLE: {item['name']} ---")
        webhook_payload = transaction_to_razorpay_webhook(item["txn"])
        print(json.dumps(webhook_payload, indent=2))
        print("\n" + "=" * 70 + "\n")
        
        # Structural assertions matching real Razorpay schemas
        assert webhook_payload["entity"] == "event"
        assert "event" in webhook_payload
        assert "payload" in webhook_payload
        assert "account_id" in webhook_payload

    print("✅ Verification Claim Passed: All 5 sample transaction categories successfully formatted as realistic Razorpay nested webhook event payloads.")

if __name__ == "__main__":
    test_sample_webhook_emissions()
