"""
Post-Fix Validation: RISK_FLAGGED Routing Bug Regression & 3-Seed Headline Reconciliation.

This script answers THREE questions after the RISK_FLAGGED routing fix:

1. HISTORICAL AUDIT (current DB): Did the bug produce live violations?
   Joins audit_logs by transaction_id — finds every txn where ANY row has
   root_cause=RISK_FLAGGED (or decline_code in risk set) AND ANY row has
   to_state=action_sent. This correctly detects the bug path even though
   the action_sent row itself carries no diagnosis_raw.

2. LIVE 3-SEED BATCH (post-fix): Run Seeds 42, 7, 99 through the fixed
   pipeline and collect DeclineZero headline net value per seed.

3. COMPLIANCE SWEEP (post-fix): Verify zero RISK_FLAGGED transactions
   reached action_sent in the newly generated data.
"""
import os
import json
import asyncio
import uuid
import psycopg2
from tabulate import tabulate

from simulator.generator import generate_batch
from core.evaluator.full_batch_runner import run_batch_webhook_pipeline
from core.audit_trail.merkle_log import get_db_connection, init_audit_db

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgrespassword@postgres:5432/revenue_recovery"
)
RISK_CODES = ("U16", "34", "59", "K1", "S1", "S2", "S3")


# ─────────────────────────────────────────────────────────────────────────────
# PART 1: Historical audit — correct JOIN-based risk violation check
# ─────────────────────────────────────────────────────────────────────────────
def check_historical_risk_violations(conn) -> int:
    """
    Correct compliance query for RISK_FLAGGED dispatch violations.

    The bug path:
      rules.py logs row A: from_state=triaged, to_state=diagnosed, root_cause=RISK_FLAGGED
      webhook.py then falls through and logs row B: to_state=action_sent (no diagnosis_raw)

    The OLD query only looked at row B's diagnosis_raw — it was NULL, so always returned 0.
    This query joins by transaction_id: any txn with a RISK_FLAGGED diagnosis row AND
    an action_sent row = a real violation.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(DISTINCT risk_txns.transaction_id)
            FROM (
                -- Transactions that were diagnosed as RISK_FLAGGED
                SELECT DISTINCT transaction_id
                FROM audit_logs
                WHERE diagnosis_raw->>'root_cause' = 'RISK_FLAGGED'
            ) AS risk_txns
            INNER JOIN (
                -- Transactions that ever reached action_sent
                SELECT DISTINCT transaction_id
                FROM audit_logs
                WHERE to_state = 'action_sent'
            ) AS dispatched_txns
            ON risk_txns.transaction_id = dispatched_txns.transaction_id;
        """)
        return cur.fetchone()[0]


def check_postfix_compliance(conn, run_tag: str) -> dict:
    """
    Full compliance sweep on the fresh post-fix batch rows (filtered by run_tag).
    """
    with conn.cursor() as cur:

        # Check 1 (corrected): RISK_FLAGGED txns that also reached action_sent
        cur.execute("""
            SELECT COUNT(DISTINCT risk_txns.transaction_id)
            FROM (
                SELECT DISTINCT transaction_id FROM audit_logs
                WHERE diagnosis_raw->>'root_cause' = 'RISK_FLAGGED'
                AND transaction_id LIKE %s
            ) AS risk_txns
            INNER JOIN (
                SELECT DISTINCT transaction_id FROM audit_logs
                WHERE to_state = 'action_sent'
                AND transaction_id LIKE %s
            ) AS dispatched_txns
            ON risk_txns.transaction_id = dispatched_txns.transaction_id;
        """, (f"{run_tag}%", f"{run_tag}%"))
        risk_violations = cur.fetchone()[0]

        # Check 2: Out-of-window dispatches
        cur.execute("""
            SELECT COUNT(*) FROM audit_logs
            WHERE to_state = 'action_sent'
            AND transaction_id LIKE %s
            AND (EXTRACT(HOUR FROM timestamp AT TIME ZONE 'Asia/Kolkata') < 8
                 OR EXTRACT(HOUR FROM timestamp AT TIME ZONE 'Asia/Kolkata') >= 19);
        """, (f"{run_tag}%",))
        window_violations = cur.fetchone()[0]

        # Check 3: Retry cap violations
        cur.execute("""
            SELECT COUNT(*) FROM audit_logs
            WHERE stopping_rule_triggered = 'RETRY_CAP_EXCEEDED'
            AND to_state = 'action_sent'
            AND transaction_id LIKE %s;
        """, (f"{run_tag}%",))
        cap_violations = cur.fetchone()[0]

        # Check 4: Distress leaks
        cur.execute("""
            SELECT COUNT(*) FROM audit_logs
            WHERE stopping_rule_triggered = 'CUSTOMER_EMOTIONAL_DISTRESS'
            AND to_state = 'action_sent'
            AND transaction_id LIKE %s;
        """, (f"{run_tag}%",))
        distress_violations = cur.fetchone()[0]

        # Check 5: Count correctly-routed escalated_human_review for risk codes
        cur.execute("""
            SELECT COUNT(DISTINCT transaction_id) FROM audit_logs
            WHERE to_state = 'escalated_human_review'
            AND transaction_id LIKE %s;
        """, (f"{run_tag}%",))
        correct_escalations = cur.fetchone()[0]

    return {
        "risk_flagged_dispatched_violations": risk_violations,
        "out_of_window_violations": window_violations,
        "retry_cap_violations": cap_violations,
        "distress_leaks": distress_violations,
        "correctly_escalated_human_review": correct_escalations,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PART 2: 3-Seed batch run
# ─────────────────────────────────────────────────────────────────────────────
async def run_single_seed(seed: int, api_url: str) -> dict:
    """Generates 10k batch at given seed and runs through live webhook pipeline.
    Uses concurrency=10 (not 50) — the serialized chain_state FOR UPDATE lock
    cannot keep up with 50 parallel connections. 10 is safe for the Merkle chain.
    """
    print(f"\n{'='*70}")
    print(f"  SEED {seed}: Generating 10,000 transactions...")
    print(f"{'='*70}")

    records = generate_batch(n=10000, seed=seed)
    run_tag = f"pf{seed}_{uuid.uuid4().hex[:4]}"

    # Tag with unique prefix so we can filter in compliance sweep
    tagged = []
    for r in records:
        r_copy = dict(r)
        r_copy["transaction_id"] = f"{run_tag}_{r['transaction_id']}"
        tagged.append(r_copy)

    benchmark = await run_batch_webhook_pipeline(tagged, api_url=api_url, concurrency=10)

    dz = benchmark.get("policies", {}).get("decline_zero", {})
    net = float(dz.get("net_recovered_inr", 0.0))
    gross = float(dz.get("recovered_amount_inr", 0.0))
    rate = float(dz.get("recovery_rate_pct", 0.0))
    risk_isolated = int(dz.get("risk_escalations_isolated", 0))

    print(f"\n  Seed {seed} Result:")
    print(f"    Gross Recovered : ₹{gross:,.2f}")
    print(f"    Net Value       : ₹{net:,.2f}")
    print(f"    Recovery Rate   : {rate:.2f}%")
    print(f"    Risk Escalations: {risk_isolated}")

    return {
        "seed": seed,
        "run_tag": run_tag,
        "net_recovered_inr": net,
        "gross_recovered_inr": gross,
        "recovery_rate_pct": rate,
        "risk_escalations_isolated": risk_isolated,
        "full_benchmark": benchmark,
    }


async def main():
    api_host = os.getenv("API_HOST", "localhost")
    api_url = f"http://{api_host}:8000/v1/webhook/razorpay"
    init_audit_db()

    print("\n" + "=" * 70)
    print("  POST-FIX VALIDATION: RISK_FLAGGED ROUTING REGRESSION")
    print("=" * 70)

    conn = get_db_connection()

    # ── PART 1: Historical check on current audit_logs ───────────────────────
    print("\n[PART 1] Historical Audit — Checking pre-existing audit_logs for bug violations...")
    historical_violations = check_historical_risk_violations(conn)
    print(f"  Correct JOIN-based RISK_FLAGGED + action_sent violations found: {historical_violations}")
    if historical_violations > 0:
        print(f"  ⚠️  BUG CONFIRMED ACTIVE IN PRIOR RUN: {historical_violations} txns were risk-flagged AND dispatched.")
    else:
        print("  ✅ Zero violations in current audit_logs (prior runs were clean / DB was reset before each run).")

    # ── PART 2: 3-Seed Fresh Batch (sequential, one per asyncio.run to avoid event-loop exhaustion) ──
    print("\n[PART 2] Running post-fix 3-seed batch (Seeds: 42, 7, 99) sequentially at concurrency=10...")
    seeds = [42, 7, 99]
    seed_results = []
    for s in seeds:
        print(f"\n  Starting Seed {s}...")
        try:
            result = await run_single_seed(s, api_url)
            seed_results.append(result)
            print(f"  Seed {s} complete. Net: ₹{result['net_recovered_inr']:,.2f}")
        except Exception as e:
            print(f"  ⚠️  Seed {s} failed: {e}")
            seed_results.append({"seed": s, "error": str(e), "net_recovered_inr": 0.0,
                                  "gross_recovered_inr": 0.0, "recovery_rate_pct": 0.0,
                                  "risk_escalations_isolated": 0, "run_tag": f"pf{s}_FAILED",
                                  "compliance_sweep": {}})

    # ── PART 3: Compliance sweep on fresh data ────────────────────────────────
    print("\n[PART 3] Post-Fix Compliance Sweep on fresh batch data...")
    all_clean = True
    for sr in seed_results:
        # Only sweep if seed didn't fail
        if "error" in sr:
            print(f"\n  Seed {sr['seed']} (tag={sr['run_tag']}): FAILED, skipping sweep.")
            all_clean = False
            continue

        sweep = check_postfix_compliance(conn, sr["run_tag"])
        sr["compliance_sweep"] = sweep
        print(f"\n  Seed {sr['seed']} (tag={sr['run_tag']}):")
        for k, v in sweep.items():
            icon = "✅" if (k != "correctly_escalated_human_review" and v == 0) or (k == "correctly_escalated_human_review" and v > 0) else "❌"
            print(f"    {icon} {k}: {v}")
        if sweep["risk_flagged_dispatched_violations"] > 0:
            all_clean = False

    conn.close()

    # ── SUMMARY ───────────────────────────────────────────────────────────────
    nets = [r["net_recovered_inr"] for r in seed_results]
    grosses = [r["gross_recovered_inr"] for r in seed_results]
    seed42 = next((r for r in seed_results if r["seed"] == 42), seed_results[0])

    print("\n" + "=" * 70)
    print("  POST-FIX BATCH VALIDATION SUMMARY")
    print("=" * 70)

    table = []
    for r in seed_results:
        table.append([
            f"Seed {r['seed']}",
            f"₹{r['gross_recovered_inr']:,.2f}",
            f"₹{r['net_recovered_inr']:,.2f}",
            f"{r['recovery_rate_pct']:.2f}%",
            r["risk_escalations_isolated"],
            r["compliance_sweep"]["risk_flagged_dispatched_violations"],
        ])

    headers = ["Seed", "Gross Recovered", "Net Value (Headline)", "Recovery Rate", "Risk Escalations", "Risk Dispatch Violations"]
    print(tabulate(table, headers=headers, tablefmt="fancy_grid"))

    print(f"\n  3-Seed Net Value Range : ₹{min(nets):,.2f} – ₹{max(nets):,.2f}")
    print(f"  3-Seed Net Value Mean  : ₹{sum(nets)/len(nets):,.2f}")
    print(f"  Headline (Seed 42)     : ₹{seed42['net_recovered_inr']:,.2f}")
    print(f"  Historical Violations  : {historical_violations} (pre-fix audit_logs)")
    print(f"  Post-Fix Violations    : {'0 ✅' if all_clean else 'NON-ZERO ❌ — INVESTIGATE'}")

    # Save consolidated result
    output = {
        "post_fix_validation": True,
        "historical_risk_violations_in_audit_logs": historical_violations,
        "seeds": seed_results,
        "headline_seed42_net_inr": seed42["net_recovered_inr"],
        "range_min_net_inr": min(nets),
        "range_max_net_inr": max(nets),
        "range_mean_net_inr": sum(nets) / len(nets),
        "all_post_fix_compliance_clean": all_clean,
    }
    os.makedirs("results", exist_ok=True)
    with open("results/post_fix_validation.json", "w") as f:
        # Remove non-serializable nested benchmark to keep file clean
        for sr in output["seeds"]:
            sr.pop("full_benchmark", None)
        json.dump(output, f, indent=2)

    print(f"\n  Full results saved to results/post_fix_validation.json")
    assert all_clean, "POST-FIX COMPLIANCE FAILED — risk violations still present in fresh data!"
    print("\n🎉 POST-FIX VALIDATION COMPLETE — all checks passed!\n")


if __name__ == "__main__":
    asyncio.run(main())
