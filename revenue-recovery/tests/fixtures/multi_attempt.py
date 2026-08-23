"""
Reusable Multi-Attempt Simulation Fixture.

Guarantees:
- Identical transaction_id across consecutive webhook submissions.
- Identical merchant_id across consecutive webhook submissions.
- Simulates realistic failure progression over time by invalidating the 24h SETNX idempotency lock
  between discrete simulated attempt intervals while strictly preserving the Redis state machine
  and cumulative retry counter across attempts.
"""
import asyncio
import httpx
from typing import Dict, Any, List, Optional
from core.state_store.redis_store import get_redis_client
from simulator.webhook_emitter import transaction_to_razorpay_webhook


async def simulate_repeated_attempts(
    transaction_record: Dict[str, Any],
    n_attempts: int = 4,
    api_url: str = "http://localhost:8000/v1/webhook/razorpay",
    merchant_id: str = "acc_RZPMerchantDemo01"
) -> List[Dict[str, Any]]:
    """
    Submits `n_attempts` consecutive payment.failed webhook events for the EXACT same transaction,
    verifying state machine and retry cap progression.
    """
    txn_id = transaction_record["transaction_id"]
    r_client = get_redis_client()
    responses = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(1, n_attempts + 1):
            # 1. Build payload ensuring exact matching IDs
            payload = transaction_to_razorpay_webhook(transaction_record, event_type="payment.failed")
            payload["account_id"] = merchant_id
            
            p_entity = payload.get("payload", {}).get("payment", {}).get("entity")
            if p_entity:
                p_entity["id"] = txn_id
                p_entity["created_at"] = 12 * 3600  # Daytime (12 PM)

            # 2. Before submitting subsequent attempts over time, clear the atomic 24h event deduplication lock
            # so the subsequent retry event is processed, but preserve the core state and attempt count in Redis!
            idemp_key = f"idemp:{merchant_id}:{txn_id}:payment.failed"
            r_client.delete(idemp_key)

            # 3. Post webhook
            resp = await client.post(api_url, json=payload)
            if resp.status_code == 200:
                responses.append(resp.json())
            else:
                responses.append({
                    "status_code": resp.status_code,
                    "error": resp.text
                })

    return responses
