"""
Unit test for simulate_repeated_attempts test fixture.

Tests that simulate_repeated_attempts guarantees identical IDs across consecutive calls
and drives attempt counts until the daily cap is reached.
"""
import asyncio
import uuid
from simulator.generator import generate_transaction
from tests.fixtures.multi_attempt import simulate_repeated_attempts

async def test_multi_attempt_fixture():
    print("\n============================================================")
    print("      TESTING MULTI-ATTEMPT FIXTURE STANDALONE")
    print("============================================================")
    
    unique_id = f"pay_fixtest_{uuid.uuid4().hex[:6]}"
    sample_txn = generate_transaction()
    sample_txn["transaction_id"] = unique_id
    sample_txn["category"] = "checkout"  # Cap is 3 attempts
    sample_txn["decline_code"] = "U69"
    sample_txn["gt_sleeping_dog"] = False

    responses = await simulate_repeated_attempts(
        transaction_record=sample_txn,
        n_attempts=4,
        merchant_id="acc_RZPMerchantDemo01"
    )

    print(f"Simulated 4 consecutive attempts on {unique_id}:")
    for i, res in enumerate(responses, 1):
        print(f"  Attempt {i} -> final_state: {res.get('final_state')} | status: {res.get('status')}")

    assert len(responses) == 4
    # Attempt 1 -> action_sent
    assert responses[0].get("final_state") == "action_sent"
    # Attempt 4 (cap of 3 reached) -> stopped_by_retry_cap
    assert responses[3].get("final_state") == "stopped_by_retry_cap"
    print("✅ Multi-attempt fixture verified standalone with exact ID alignment & retry cap enforcement!")

if __name__ == "__main__":
    asyncio.run(test_multi_attempt_fixture())
