"""
Phase 2a Unit Test: State Machine Transition Logic & Validation.

Tests legal and illegal state transitions across the 14-state lifecycle graph.
"""
from api.models.transaction import TransactionState, is_valid_transition, VALID_TRANSITIONS

def test_state_transitions():
    print("\n--- Running Phase 2a State Machine Unit Tests ---")
    
    # 1. Valid Transitions that MUST pass
    valid_test_cases = [
        (TransactionState.RECEIVED, TransactionState.TRIAGED),
        (TransactionState.TRIAGED, TransactionState.PASSIVE_HOLD),
        (TransactionState.TRIAGED, TransactionState.DIAGNOSED),
        (TransactionState.TRIAGED, TransactionState.DO_NOT_DISTURB),
        (TransactionState.PASSIVE_HOLD, TransactionState.RESOLVED_SUCCESS),
        (TransactionState.PASSIVE_HOLD, TransactionState.DIAGNOSED),
        (TransactionState.DIAGNOSED, TransactionState.ACTION_SENT),
        (TransactionState.DIAGNOSED, TransactionState.AMBIGUOUS_ESCALATED),
        (TransactionState.DIAGNOSED, TransactionState.ESCALATED_HUMAN_REVIEW),
        (TransactionState.DIAGNOSED, TransactionState.STOPPED_BY_CONTACT_WINDOW),
        (TransactionState.ACTION_SENT, TransactionState.RESOLVED_SUCCESS),
        (TransactionState.ACTION_SENT, TransactionState.STOPPED_BY_EMOTIONAL_DISTRESS),
        (TransactionState.STOPPED_BY_CONTACT_WINDOW, TransactionState.ACTION_SENT),
    ]

    print("\nTesting Valid Transitions:")
    for from_st, to_st in valid_test_cases:
        result = is_valid_transition(from_st, to_st)
        assert result is True, f"Failed: {from_st} -> {to_st} should be valid!"
        print(f"  [PASS] {from_st.value:<26} ──► {to_st.value:<26} (Valid)")

    # 2. Invalid Transitions that MUST fail
    invalid_test_cases = [
        (TransactionState.RECEIVED, TransactionState.RESOLVED_SUCCESS),   # Skipping triage/diagnosis
        (TransactionState.RECEIVED, TransactionState.ACTION_SENT),        # Action before diagnosis
        (TransactionState.TRIAGED, TransactionState.RESOLVED_SUCCESS),    # Cannot resolve without diagnosis/hold
        (TransactionState.RESOLVED_SUCCESS, TransactionState.TRIAGED),    # Terminal state cannot reopen
        (TransactionState.RESOLVED_FAILED, TransactionState.ACTION_SENT), # Terminal state cannot retry
        (TransactionState.ESCALATED_HUMAN_REVIEW, TransactionState.ACTION_SENT), # Risk-flagged cannot auto-retry
        (TransactionState.DO_NOT_DISTURB, TransactionState.ACTION_SENT),  # Sleeping dog cannot be contacted
        (TransactionState.AMBIGUOUS_ESCALATED, TransactionState.ACTION_SENT), # Ambiguous cannot auto-dispatch
    ]

    print("\nTesting Invalid Transitions (Illegal state jumps):")
    for from_st, to_st in invalid_test_cases:
        result = is_valid_transition(from_st, to_st)
        assert result is False, f"Failed: {from_st} -> {to_st} should be rejected!"
        print(f"  [PASS] {from_st.value:<26} ──X {to_st.value:<26} (Correctly Rejected)")

    print("\n✅ Verification Claim Passed: All valid transitions permitted and all illegal jumps strictly rejected.")

if __name__ == "__main__":
    test_state_transitions()
