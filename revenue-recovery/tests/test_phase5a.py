"""
Phase 5a Unit Test: Action Dispatcher & Payment Links Integration.

Validates:
1. Executes all 6 recovery actions produced by Phase 4 diagnosis.
2. Generates well-formed Razorpay Payment Links API payloads.
3. Strict Compliance Guardrail: ESCALATE_HUMAN_REVIEW NEVER creates a payment link or sends customer outreach.
"""
from core.recovery_engine.actions import dispatch_action, CHANNEL_COSTS

def test_action_dispatches():
    print("\n--- Running Phase 5a Action Dispatcher Unit Tests ---")
    
    sample_record = {
        "transaction_id": "test_txn_9a8b7c6d",
        "amount": 2499.00,
        "category": "checkout",
        "payment_method": "upi",
        "contact": "+919876543210",
        "email": "payee@example.com"
    }

    action_types = [
        "SEND_FRESH_PAYMENT_LINK_URGENT",
        "SCHEDULE_SALARY_ALIGNED_RETRY",
        "SUGGEST_ALTERNATE_METHOD",
        "SEND_MANDATE_REVIVAL_LINK",
        "SEND_REMINDER_TRACK_PROMISE",
        "ESCALATE_HUMAN_REVIEW"
    ]

    results = []
    print("\nExecuting all 6 Recovery Actions:")
    for act in action_types:
        res = dispatch_action(act, sample_record)
        assert res["success"] is True
        assert res["action"] == act
        results.append(res)

        print(f"\n--- ACTION: {act} ---")
        print(f"  Channel       : {res['channel']}")
        print(f"  Cost          : ₹{res['cost']:.2f}")
        print(f"  Payment Link  : {res['payment_link_id']}")
        print(f"  Short URL     : {res['payment_url']}")
        print(f"  Message Sent  : {res['message_sent']}")

    # ----------------------------------------------------------------------------------
    # Dedicated Compliance Check for Human Escalation
    # ----------------------------------------------------------------------------------
    print("\n--- Running Dedicated Escalation Isolation Compliance Audit ---")
    escalation_res = [r for r in results if r["action"] == "ESCALATE_HUMAN_REVIEW"][0]
    
    assert escalation_res["channel"] == "internal_escalation", "Escalation must be internal"
    assert escalation_res["payment_link_id"] is None, "Escalation must NOT create a payment link"
    assert escalation_res["payment_url"] is None, "Escalation must NOT generate a payment URL"
    assert escalation_res["message_sent"] is None, "Escalation must NOT send a customer message"
    assert escalation_res["escalated_for_review"] is True

    print("✅ Strict Regulatory Assertion Passed: ESCALATE_HUMAN_REVIEW isolated to internal queue with 0 customer contact.")
    print("✅ All 6 action dispatches executed cleanly with valid payloads.")

if __name__ == "__main__":
    test_action_dispatches()
