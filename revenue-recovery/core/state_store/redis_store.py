"""
Redis State Storage & Idempotency Lock Layer for AI Revenue Recovery.

Provides:
- In-memory lifecycle state persistence (txn:{txn_id})
- Strict state transition enforcement via VALID_TRANSITIONS
- Atomic 24-hour TTL idempotency locking (idemp:{merchant_id}:{txn_id}:{event_type})
"""
import os
import json
from typing import Optional, Dict, Any
import redis

from api.models.transaction import TransactionState, is_valid_transition

# Connect to Redis using environment URL or local fallback
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """
    Returns a shared Redis client instance.
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def get_state(txn_id: str) -> Optional[Dict[str, Any]]:
    """
    Reads the active JSON state blob at key txn:{txn_id}.
    Returns None if key does not exist.
    """
    r = get_redis_client()
    raw = r.get(f"txn:{txn_id}")
    if raw is None:
        return None
    return json.loads(raw)


def set_state(txn_id: str, state: TransactionState | str, ttl_seconds: int = 86400 * 7, **fields) -> Dict[str, Any]:
    """
    Writes or updates the active transaction state payload in Redis.
    """
    r = get_redis_client()
    state_str = state.value if isinstance(state, TransactionState) else str(state)
    
    current = get_state(txn_id) or {
        "state": state_str,
        "attempt_count": 0,
        "priority_score": None,
        "cate_score": None,
        "category": fields.get("category", "checkout")
    }

    current["state"] = state_str
    for k, v in fields.items():
        current[k] = v

    r.set(f"txn:{txn_id}", json.dumps(current), ex=ttl_seconds)
    return current


def transition_state(txn_id: str, new_state: TransactionState | str) -> Dict[str, Any]:
    """
    Strict state transition validator.
    Reads current state from Redis, asserts transition is legally permitted via VALID_TRANSITIONS,
    and updates state. Raises ValueError if the transition is illegal.
    """
    target_state = TransactionState(new_state) if isinstance(new_state, str) else new_state
    current_data = get_state(txn_id)

    if current_data is None:
        # Initial transition when record has not yet been saved in Redis
        current_state = TransactionState.RECEIVED
        set_state(txn_id, current_state)
    else:
        current_state = TransactionState(current_data["state"])

    if not is_valid_transition(current_state, target_state):
        raise ValueError(
            f"Illegal state transition requested for txn:{txn_id}: "
            f"'{current_state.value}' ──X '{target_state.value}' is not permitted in VALID_TRANSITIONS graph."
        )

    return set_state(txn_id, target_state)


def acquire_idempotency_lock(
    transaction_id: str,
    merchant_id: str,
    event_type: str,
    ttl_seconds: int = 86400
) -> bool:
    """
    Acquires an atomic idempotency lock via Redis SETNX with a 24-hour TTL.
    
    Key structure: idemp:{merchant_id}:{transaction_id}:{event_type}
    
    Returns:
    - True: Lock acquired successfully (first-time processing, proceed).
    - False: Lock already exists (duplicate webhook within 24h, discard/skip).
    
    Design rationale for TTL expiry without manual release:
    Webhook deduplication protects against automated retries replayed minutes or hours later.
    Releasing the lock immediately upon completion would leave the system vulnerable to duplicate
    dispatches if a delayed retry arrives later.
    """
    r = get_redis_client()
    lock_key = f"idemp:{merchant_id}:{transaction_id}:{event_type}"
    
    # Atomic SETNX with expiration
    acquired = r.set(lock_key, "locked", nx=True, ex=ttl_seconds)
    return bool(acquired)
