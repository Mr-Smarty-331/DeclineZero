"""
Append-Only SHA-256 Hash Chained Audit Log.

Provides tamper-evident cryptographic auditability:
1. Leaf Hash: SHA256(txn_id | timestamp | diagnosis | action | stopping_rule)
2. Chain Hash: SHA256(prev_chain_hash + leaf_hash)
3. Concurrency Safety: Row lock (SELECT ... FOR UPDATE) on chain_state table in Postgres.
"""
import os
import json
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgrespassword@postgres:5432/revenue_recovery")
GENESIS_HASH = "0" * 64


def get_db_connection():
    """
    Returns a fresh Postgres connection.
    """
    return psycopg2.connect(DATABASE_URL)


def init_audit_db():
    """
    Initializes audit_logs and chain_state tables in Postgres.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. Running chain state table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chain_state (
                    id INT PRIMARY KEY DEFAULT 1,
                    running_hash VARCHAR(64) NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Seed Genesis Hash if empty
            cur.execute("SELECT running_hash FROM chain_state WHERE id = 1;")
            row = cur.fetchone()
            if not row:
                cur.execute("""
                    INSERT INTO chain_state (id, running_hash)
                    VALUES (1, %s)
                    ON CONFLICT (id) DO NOTHING;
                """, (GENESIS_HASH,))

            # 2. Audit logs append-only ledger
            cur.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    seq_id BIGSERIAL,
                    id UUID PRIMARY KEY,
                    transaction_id VARCHAR(128) NOT NULL,
                    from_state VARCHAR(64),
                    to_state VARCHAR(64) NOT NULL,
                    priority_score FLOAT,
                    cate_score FLOAT,
                    diagnosis_raw JSONB,
                    action_taken VARCHAR(128),
                    stopping_rule_triggered VARCHAR(128),
                    cost_of_action NUMERIC(10, 2) DEFAULT 0.00,
                    leaf_hash VARCHAR(64) NOT NULL,
                    chain_hash VARCHAR(64) NOT NULL,
                    timestamp TIMESTAMP WITH TIME ZONE NOT NULL
                );
                ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS seq_id BIGSERIAL;
                CREATE INDEX IF NOT EXISTS idx_audit_txn ON audit_logs(transaction_id);
                CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs(timestamp);
                CREATE INDEX IF NOT EXISTS idx_audit_seq ON audit_logs(seq_id);
            """)
        conn.commit()
    finally:
        conn.close()


def compute_leaf(
    txn_id: str,
    timestamp: str,
    diagnosis: str,
    action: str,
    stopping_rule: str
) -> str:
    """
    Computes the canonical SHA-256 leaf hash for an audit transition event.
    """
    payload = f"{txn_id}|{timestamp}|{diagnosis}|{action}|{stopping_rule}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def log_transition(
    txn_id: str,
    to_state: str,
    from_state: Optional[str] = None,
    diagnosis_raw: Optional[Dict[str, Any]] = None,
    action_taken: Optional[str] = None,
    stopping_rule_triggered: Optional[str] = None,
    priority_score: Optional[float] = None,
    cate_score: Optional[float] = None,
    cost_of_action: float = 0.0,
    timestamp: Optional[datetime] = None
) -> str:
    """
    Appends a transition record to Postgres under a SELECT ... FOR UPDATE row lock on chain_state.
    Returns the newly computed chain_hash.
    """
    if timestamp is None:
        ts = datetime.now(timezone.utc)
    else:
        ts = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)

    ts_iso = ts.isoformat()
    diag_str = json.dumps(diagnosis_raw, sort_keys=True) if diagnosis_raw else "NONE"
    act_str = str(action_taken or "NONE")
    stop_str = str(stopping_rule_triggered or "NONE")

    leaf_hash = compute_leaf(txn_id, ts_iso, diag_str, act_str, stop_str)
    log_id = str(uuid.uuid4())

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Concurrency-safe lock on the singleton chain_state row
            cur.execute("SELECT running_hash FROM chain_state WHERE id = 1 FOR UPDATE;")
            row = cur.fetchone()
            if row:
                prev_hash = row[0]
            else:
                prev_hash = GENESIS_HASH

            # Compute next chain hash: SHA256(prev_hash + leaf_hash)
            new_chain_hash = hashlib.sha256((prev_hash + leaf_hash).encode("utf-8")).hexdigest()

            # Append to audit log
            cur.execute("""
                INSERT INTO audit_logs (
                    id, transaction_id, from_state, to_state, priority_score, cate_score,
                    diagnosis_raw, action_taken, stopping_rule_triggered, cost_of_action,
                    leaf_hash, chain_hash, timestamp
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                );
            """, (
                log_id,
                txn_id,
                from_state,
                to_state,
                priority_score,
                cate_score,
                json.dumps(diagnosis_raw) if diagnosis_raw else None,
                action_taken,
                stopping_rule_triggered,
                cost_of_action,
                leaf_hash,
                new_chain_hash,
                ts
            ))

            # Advance running hash
            cur.execute("""
                UPDATE chain_state
                SET running_hash = %s, updated_at = %s
                WHERE id = 1;
            """, (new_chain_hash, ts))

        conn.commit()
        return new_chain_hash
    finally:
        conn.close()


def get_current_chain_hash() -> str:
    """
    Reads the current top-of-chain hash from chain_state.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT running_hash FROM chain_state WHERE id = 1;")
            row = cur.fetchone()
            return row[0] if row else GENESIS_HASH
    finally:
        conn.close()


def get_audit_history(txn_id: str) -> List[Dict[str, Any]]:
    """
    Fetches chronological audit transitions for a given transaction.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM audit_logs
                WHERE transaction_id = %s
                ORDER BY timestamp ASC;
            """, (txn_id,))
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


# Auto-initialize database tables upon import
try:
    init_audit_db()
except Exception as e:
    # Will initialize when database container is ready
    pass
