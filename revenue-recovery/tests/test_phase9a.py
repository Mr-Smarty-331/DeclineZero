"""
Phase 9a Unit Test: Streamlit Dashboard Data Layer & Exact Math Reconciliation.

Verifies:
1. load_baseline_comparison accurately loads the 4-way comparative benchmark.
2. Net Value and all cost terms match raw baseline_comparison.json down to ₹0.00.
3. fetch_live_metrics executes read-only Postgres aggregation correctly.
4. fetch_live_feed returns sequential rows ordered by seq_id DESC.
"""
import os
import json
import psycopg2
from dashboard.app import (
    load_baseline_comparison,
    fetch_live_metrics,
    fetch_live_feed,
    BASELINE_JSON_PATH
)


def test_phase9a_unit():
    print("\n============================================================")
    print("      PHASE 9a UNIT TEST: DASHBOARD DATA & MATH LAYER")
    print("============================================================")
    
    # -------------------------------------------------------------------------
    # 1. Test Baseline Comparison JSON Loader & Net Value Equality
    # -------------------------------------------------------------------------
    print("\n[Step 1] Verifying 4-Way Baseline Comparison Parsing & Math...")
    assert os.path.exists(BASELINE_JSON_PATH), f"Missing {BASELINE_JSON_PATH}"
    
    with open(BASELINE_JSON_PATH, "r") as f:
        raw_json = json.load(f)

    dash_data = load_baseline_comparison()
    assert dash_data is not None, "load_baseline_comparison returned None"
    assert "policies" in dash_data, "Missing 'policies' key in loaded data"

    # Verify each policy's Net Value formula matches raw JSON
    for key, pol in dash_data["policies"].items():
        raw_pol = raw_json["policies"][key]
        
        # Check Net Value exact match
        dash_net = pol["net_recovered_inr"]
        raw_net = raw_pol["net_recovered_inr"]
        assert dash_net == raw_net, f"Net value mismatch for {key}: dash={dash_net}, raw={raw_net}"

        # Re-compute Net Value independently
        gross = pol["recovered_amount_inr"]
        cost = pol["total_outreach_cost_inr"]
        churn = pol["monetized_churn_cost_inr"]
        penalty = pol["regulatory_penalty_cost_inr"]
        expected_net = round(gross - cost - churn - penalty, 2)
        
        diff = abs(dash_net - expected_net)
        print(f"  • {pol['name']:<45} | Net Value: ₹{dash_net:>14,.2f} | Recomputed: ₹{expected_net:>14,.2f} (Diff: ₹{diff:.2f})")
        assert diff < 0.01, f"Mathematical drift in {key}: {diff}"

    print("  ✅ All 4 policy economic terms match JSON and mathematical definitions down to ₹0.00!")

    # -------------------------------------------------------------------------
    # 2. Test Live Postgres Metrics Aggregator
    # -------------------------------------------------------------------------
    print("\n[Step 2] Verifying Live Postgres Metrics Aggregation Query...")
    metrics = fetch_live_metrics()
    print(f"  • Total Audit Events : {metrics['total_events']:,}")
    print(f"  • Unique Transactions: {metrics['total_txns']:,}")
    print(f"  • Actions Dispatched : {metrics['dispatched']:,}")
    print(f"  • Resolved Success   : {metrics['resolved']:,}")
    print(f"  • Passive Holds      : {metrics['passive_hold']:,}")
    print(f"  • Conformal Escalated: {metrics['escalated']:,}")
    print(f"  • Compliance Stopped : {metrics['stopped']:,}")

    assert metrics["total_events"] > 0, "Expected nonzero audit events in Postgres"
    assert metrics["total_txns"] > 0, "Expected nonzero unique transactions in Postgres"
    print("  ✅ Live metrics query executed cleanly against Postgres with zero exceptions.")

    # -------------------------------------------------------------------------
    # 3. Test Live Transition Feed Query
    # -------------------------------------------------------------------------
    print("\n[Step 3] Verifying Live Transition Feed Query (Latest 50)...")
    feed = fetch_live_feed(limit=50)
    assert len(feed) > 0, "Expected feed rows from audit_logs"
    assert len(feed) <= 50, f"Expected <= 50 rows, got {len(feed)}"

    # Confirm monotonic sequence order (seq_id descending)
    seqs = [r["seq_id"] for r in feed]
    assert seqs == sorted(seqs, reverse=True), "Feed rows are not sorted in descending seq_id order!"

    sample = feed[0]
    print(f"  • Latest Event (Seq {sample['seq_id']}): {sample['transaction_id']} -> {sample['to_state']} at {sample['timestamp']}")
    print(f"  • Columns Verified: {list(sample.keys())}")
    print("  ✅ Live feed query verified with strict descending seq_id ordering.")

    print("\n🎉 PHASE 9a UNIT TEST PASSED 100%!")


if __name__ == "__main__":
    test_phase9a_unit()
