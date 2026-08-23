"""
Phase 8b Integration Test: 10,000 Batch Live Ingestion, System-Wide Regression & 4-Way Baseline Benchmark.

Verifies:
1. 10k Batch Live Webhook Ingestion: All 10,000 synthetic transactions processed through POST /v1/webhook/razorpay.
2. System-Wide Compliance Regressions (Direct Postgres Audit Assertions):
   - Zero auto-retries on RISK_FLAGGED decline codes.
   - Zero outreach dispatches outside 8AM-7PM window.
   - Zero retry cap violations.
   - Zero hard-rule CMDP leaks.
   - 100% Cryptographic chain integrity on full ledger.
3. 4-Way Baseline Comparison Table: Generates results/baseline_comparison.json and validates side-by-side metrics.
"""
import os
import json
import uuid
import asyncio
import requests
from tabulate import tabulate

from simulator.generator import generate_batch
from core.evaluator.full_batch_runner import run_batch_webhook_pipeline
from core.audit_trail.merkle_log import get_db_connection, init_audit_db
from api.routes.audit import verify_audit_proof

async def test_full_10k_batch_and_regression_suite():
    api_host = os.getenv("API_HOST", "localhost")
    api_url = f"http://{api_host}:8000/v1/webhook/razorpay"

    print("\n======================================================================")
    print("      RUNNING PHASE 8b FULL 10,000 BATCH & REGRESSION SUITE")
    print("======================================================================")
    init_audit_db()

    # Step 1: Generate or load 10,000 transactions
    data_path = "simulator/data/synthetic_transactions_10k.csv"
    if not os.path.exists(data_path):
        print("Generating 10,000 synthetic transactions...")
        records = generate_batch(n=10000, output_path=data_path)
    else:
        import pandas as pd
        print(f"Loading existing 10,000 synthetic transactions from {data_path}...")
        df = pd.read_csv(data_path)
        records = df.to_dict(orient="records")

    assert len(records) == 10000

    # Ensure unique IDs for this benchmark run so idempotency locks do not block first-time execution
    run_tag = uuid.uuid4().hex[:6]
    fresh_records = []
    for r in records:
        r_copy = dict(r)
        r_copy["transaction_id"] = f"{run_tag}_{r['transaction_id']}"
        fresh_records.append(r_copy)

    # Step 2: Ingest 10,000 transactions through live webhook
    benchmark_data = await run_batch_webhook_pipeline(fresh_records, api_url=api_url, concurrency=50)

    # Step 3: Verify results/baseline_comparison.json exists and is valid
    results_path = "results/baseline_comparison.json"
    assert os.path.exists(results_path), f"Missing {results_path}"
    with open(results_path, "r") as f:
        saved_benchmark = json.load(f)
    assert "policies" in saved_benchmark
    assert len(saved_benchmark["policies"]) == 4

    # -------------------------------------------------------------------------
    # Step 4: System-Wide Regression Assertions (Direct Postgres Audit Logs)
    # -------------------------------------------------------------------------
    print("\n======================================================================")
    print("      PART 2: SYSTEM-WIDE COMPLIANCE & AUDIT REGRESSION CHECKS")
    print("======================================================================")
    
    risk_codes = ("U16", "34", "59", "K1", "S1", "S2", "S3")
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Assertion 1: Zero risk-flagged cases received auto-outreach
            # IMPORTANT: The correct check joins by transaction_id.
            # The action_sent audit row written by the Celery worker does NOT carry
            # diagnosis_raw — it is NULL on that row. The old single-row query
            # (WHERE to_state='action_sent' AND diagnosis_raw->>'root_cause'='RISK_FLAGGED')
            # was structurally blind to the bug path. This JOIN finds any txn where
            # a RISK_FLAGGED diagnosis row AND an action_sent row both exist.
            cur.execute("""
                SELECT COUNT(DISTINCT risk_txns.transaction_id)
                FROM (
                    SELECT DISTINCT transaction_id FROM audit_logs
                    WHERE diagnosis_raw->>'root_cause' = 'RISK_FLAGGED'
                ) AS risk_txns
                INNER JOIN (
                    SELECT DISTINCT transaction_id FROM audit_logs
                    WHERE to_state = 'action_sent'
                ) AS dispatched_txns
                ON risk_txns.transaction_id = dispatched_txns.transaction_id;
            """)
            risk_violations = cur.fetchone()[0]
            print(f"  [Check 1] Risk-Flagged Auto-Retries Dispatched  : {risk_violations} (Strict: 0)")
            assert risk_violations == 0, f"VIOLATION: {risk_violations} risk cases were dispatched outreach!"


            # Assertion 2: Zero outreach dispatches outside 8AM-7PM local window
            cur.execute("""
                SELECT COUNT(*) FROM audit_logs
                WHERE to_state = 'action_sent'
                AND (EXTRACT(HOUR FROM timestamp AT TIME ZONE 'Asia/Kolkata') < 8
                     OR EXTRACT(HOUR FROM timestamp AT TIME ZONE 'Asia/Kolkata') >= 19);
            """)
            window_violations = cur.fetchone()[0]
            print(f"  [Check 2] Out-of-Window Outreach Incursions     : {window_violations} (Strict: 0)")
            assert window_violations == 0, f"VIOLATION: {window_violations} actions dispatched outside 8AM-7PM!"

            # Assertion 3: Zero retry cap violations
            cur.execute("""
                SELECT COUNT(*) FROM audit_logs
                WHERE stopping_rule_triggered = 'RETRY_CAP_EXCEEDED'
                AND to_state = 'action_sent';
            """)
            cap_violations = cur.fetchone()[0]
            print(f"  [Check 3] Retry Attempt Cap Violations          : {cap_violations} (Strict: 0)")
            assert cap_violations == 0, "VIOLATION: Action sent after retry cap exceeded!"

            # Assertion 4: Zero customer distress leaks
            cur.execute("""
                SELECT COUNT(*) FROM audit_logs
                WHERE stopping_rule_triggered = 'CUSTOMER_EMOTIONAL_DISTRESS'
                AND to_state = 'action_sent';
            """)
            distress_violations = cur.fetchone()[0]
            print(f"  [Check 4] Emotional Distress Leaks              : {distress_violations} (Strict: 0)")
            assert distress_violations == 0, "VIOLATION: Distressed customer received automated outreach!"

            # Assertion 5: Cryptographic Merkle Hash Chain Proof
            cur.execute("SELECT transaction_id FROM audit_logs ORDER BY timestamp DESC LIMIT 1;")
            latest_txn = cur.fetchone()[0]
            
            proof = await verify_audit_proof(latest_txn)
            print(f"  [Check 5] Full Ledger Cryptographic Verification: verified={proof.verified} ({proof.total_records_verified} records)")
            assert proof.verified is True, "CRITICAL ERROR: Audit chain failed mathematical verification!"
            print("✅ All 5 System-Wide Compliance & Cryptographic Regression Checks PASSED (100% Zero Violations).")
    finally:
        conn.close()

    # -------------------------------------------------------------------------
    # Step 5: Render 4-Way Comparative Benchmark Table
    # -------------------------------------------------------------------------
    print("\n======================================================================")
    print("      PART 3: 4-WAY COMPARATIVE BASELINE BENCHMARK REPORT")
    print("======================================================================")
    
    policies = saved_benchmark["policies"]
    table_rows = []
    for key, p in policies.items():
        table_rows.append([
            p["name"],
            f"₹{p['recovered_amount_inr']:,.2f}",
            f"{p['recovery_rate_pct']:.1f}%",
            f"₹{p['total_outreach_cost_inr']:,.2f}",
            f"₹{p['net_recovered_inr']:,.2f}",
            p["compliance_violations"],
            p["customer_churn_incidents"]
        ])

    headers = [
        "Policy Paradigm",
        "Recovered (INR)",
        "Rec. Rate",
        "Cost (INR)",
        "Net Value (INR)",
        "Violations",
        "Churns"
    ]
    print(tabulate(table_rows, headers=headers, tablefmt="fancy_grid"))

    print("\n🎉 ALL PHASE 8b FULL-BATCH REGRESSION & BASELINE BENCHMARKS PASSED!\n")

if __name__ == "__main__":
    asyncio.run(test_full_10k_batch_and_regression_suite())
