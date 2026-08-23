"""
Phase 6a Unit Test: CMDP Value Iteration Convergence & Intuitive Policy Invariants.

Validates:
1. Value Iteration Convergence: Verifies Bellman optimality convergence with Δ < 1e-4.
2. Exhaustion Invariant: attempts_remaining=0 ALWAYS maps to 'stop'.
3. Distress Protection Invariant: sentiment='distressed' NEVER allows active outreach (strictly maps to 'stop' or non-intrusive 'wait_48h').
4. High vs Low LTV Discrimination: High-LTV fresh neutral states favor active outreach, whereas low-LTV negative states stop.
"""
from policy.value_iteration import run_value_iteration, load_stopping_policy
from policy.mdp_definition import state_to_key, DAYS_SINCE_FAILURE, LTV_TIERS, SENTIMENTS

def test_value_iteration_and_invariants():
    print("\n--- Running Phase 6a CMDP Value Iteration Unit Tests ---")
    
    # 1. Run Value Iteration
    V_star, policy, iters, delta = run_value_iteration(gamma=0.95, theta=1e-4)

    print(f"\nConvergence Metrics:")
    print(f" - Total Iterations: {iters}")
    print(f" - Final Value Delta (Δ): {delta:.7f} (Target < 0.000100)")
    assert delta <= 1e-4, f"Value iteration failed to converge within tolerance: delta={delta}"

    # -------------------------------------------------------------------------
    # Invariant 1: attempts_remaining == 0 MUST ALWAYS map to "stop"
    # -------------------------------------------------------------------------
    print("\nEvaluating Invariant 1 (Attempt Exhaustion -> 'stop'):")
    zero_attempt_violations = 0
    for days in DAYS_SINCE_FAILURE:
        for ltv in LTV_TIERS:
            for sent in SENTIMENTS:
                k = state_to_key((0, days, ltv, sent))
                act = policy[k]
                if act != "stop":
                    zero_attempt_violations += 1
    assert zero_attempt_violations == 0, f"Found {zero_attempt_violations} states with 0 attempts not mapped to 'stop'"
    print("  [PASS] 100% of states with attempts_remaining=0 strictly map to 'stop'.")

    # -------------------------------------------------------------------------
    # Invariant 2: sentiment == "distressed" MUST NEVER perform active outreach
    # -------------------------------------------------------------------------
    print("\nEvaluating Invariant 2 (Customer Distress Protection -> 'stop' or 'wait_48h'):")
    intrusive_outreach_violations = 0
    distress_act_counts = {"stop": 0, "wait_48h": 0}
    for attempts in range(1, 9):
        for days in DAYS_SINCE_FAILURE:
            for ltv in LTV_TIERS:
                k = state_to_key((attempts, days, ltv, "distressed"))
                act = policy[k]
                if act in ("urgent_whatsapp", "voice_nudge", "salary_deferred_sms"):
                    intrusive_outreach_violations += 1
                else:
                    distress_act_counts[act] += 1
    assert intrusive_outreach_violations == 0, f"Found {intrusive_outreach_violations} distressed states with intrusive outreach"
    print(f"  [PASS] Zero active outreach on distressed customers ({distress_act_counts['stop']} stop, {distress_act_counts['wait_48h']} cooling-off wait_48h).")

    # -------------------------------------------------------------------------
    # Invariant 3: High LTV vs Low LTV Discrimination
    # -------------------------------------------------------------------------
    print("\nEvaluating Invariant 3 (LTV & Recency Discrimination):")
    
    # State A: High LTV, 5 attempts left, fresh failure (0-2d), neutral sentiment
    key_high_fresh = state_to_key((5, "0-2", "high", "neutral"))
    act_high_fresh = policy[key_high_fresh]
    val_high_fresh = V_star[key_high_fresh]
    print(f"  - High LTV Fresh (5 attempts, 0-2d, high, neutral)  ──► Action: {act_high_fresh:<20} | Expected Value: ₹{val_high_fresh:.2f}")
    assert act_high_fresh in ("urgent_whatsapp", "voice_nudge", "salary_deferred_sms"), f"High LTV fresh should outreach, got {act_high_fresh}"

    # State B: Low LTV, 1 attempt left, stale failure (8-30d), negative sentiment
    key_low_stale = state_to_key((1, "8-30", "low", "negative"))
    act_low_stale = policy[key_low_stale]
    val_low_stale = V_star[key_low_stale]
    print(f"  - Low LTV Stale (1 attempt, 8-30d, low, negative)   ──► Action: {act_low_stale:<20} | Expected Value: ₹{val_low_stale:.2f}")
    assert act_low_stale in ("stop", "wait_48h"), f"Low LTV stale should stop or wait, got {act_low_stale}"

    print("\n✅ Verification Claim Passed: Value iteration converged cleanly and policy matches intuitive financial/relationship trade-offs.")

if __name__ == "__main__":
    test_value_iteration_and_invariants()
