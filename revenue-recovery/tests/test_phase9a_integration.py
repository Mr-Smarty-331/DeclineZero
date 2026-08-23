"""
Phase 9a Integration Test: Real-Time Webhook Pipeline to Dashboard Live Feed Seam.

Verifies:
1. Submitting 100 fresh live webhook transactions through /v1/webhook/razorpay.
2. Dashboard layer (fetch_live_metrics, fetch_live_feed) immediately reflects the new transactions.
3. No connection errors, stale reads, or schema mismatches across the Docker network.
"""
import asyncio
import uuid
import httpx
from simulator.generator import generate_transaction
from simulator.webhook_emitter import transaction_to_razorpay_webhook
from dashboard.app import fetch_live_metrics, fetch_live_feed


async def test_phase9a_integration():
    print("\n============================================================")
    print("      PHASE 9a INTEGRATION TEST: REAL-TIME STREAM SEAM")
    print("============================================================")
    
    # 1. Capture initial baseline counts
    initial_metrics = fetch_live_metrics()
    print(f"\n[Step 1] Initial State:")
    print(f"  • Total Events in DB : {initial_metrics['total_events']:,}")
    print(f"  • Unique Transactions: {initial_metrics['total_txns']:,}")

    # 2. Generate 100 fresh live transactions
    tag = uuid.uuid4().hex[:6]
    print(f"\n[Step 2] Generating 100 fresh transactions (Tag: {tag})...")
    fresh_txns = []
    for i in range(100):
        txn = generate_transaction()
        txn["transaction_id"] = f"live_dash_{tag}_{i}_{txn['category']}"
        fresh_txns.append(txn)

    # 3. Post through real HTTP webhook endpoint
    api_url = "http://localhost:8000/v1/webhook/razorpay"
    print(f"\n[Step 3] Emitting 100 transactions to live API at {api_url}...")
    
    dispatched_ids = set()
    async with httpx.AsyncClient(timeout=10.0) as client:
        for txn in fresh_txns:
            payload = transaction_to_razorpay_webhook(txn, "payment.failed")
            resp = await client.post(api_url, json=payload)
            assert resp.status_code == 200, f"Webhook failed: {resp.status_code} - {resp.text}"
            data = resp.json()
            dispatched_ids.add(data["transaction_id"])

    print(f"  ✅ 100/100 Webhooks successfully processed with HTTP 200.")

    # 4. Verify Dashboard query layer immediately sees the new transactions
    print(f"\n[Step 4] Checking Dashboard Live Queries against Postgres...")
    updated_metrics = fetch_live_metrics()
    print(f"  • Updated Total Events : {updated_metrics['total_events']:,} (Delta: +{updated_metrics['total_events'] - initial_metrics['total_events']})")
    print(f"  • Updated Unique Txns  : {updated_metrics['total_txns']:,} (Delta: +{updated_metrics['total_txns'] - initial_metrics['total_txns']})")

    assert updated_metrics["total_txns"] >= initial_metrics["total_txns"] + 100, "Dashboard failed to detect 100 new transactions!"

    # 5. Verify Latest Feed contains the new transactions
    print(f"\n[Step 5] Verifying Live Feed Top 50 Entries...")
    feed = fetch_live_feed(limit=50)
    found_count = sum(1 for r in feed if r["transaction_id"] in dispatched_ids)
    print(f"  • Found {found_count}/50 newly emitted transactions in top 50 feed rows.")
    assert found_count > 0, "None of the newly emitted transactions appeared in top 50 live feed!"

    sample = next(r for r in feed if r["transaction_id"] in dispatched_ids)
    print(f"  • Sample Verified Live Event: Seq #{sample['seq_id']} | ID: {sample['transaction_id']} | State: {sample['to_state']}")
    print("\n🎉 PHASE 9a INTEGRATION TEST PASSED 100%!")


if __name__ == "__main__":
    asyncio.run(test_phase9a_integration())
