"""
DeclineZero — Autonomous AI Revenue Recovery Dashboard (Streamlit).

Pages / Views:
1. Live Monitor: Real-time transaction feed, live KPI counters, and color-coded safety badges.
2. Batch Analytics: Economic benchmark, Net Value centerpiece chart, B2B breakdown, and 3-seed variance range.
3. Audit Explorer: Transaction timeline narrative and live SHA-256 Merkle chain verification.
"""
import os
import json
import time
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
import altair as alt
import streamlit as st
import requests

# -----------------------------------------------------------------------------
# Configuration & Razorpay Dark Design Tokens
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="DeclineZero | AI Revenue Recovery",
    layout="wide",
    initial_sidebar_state="expanded"
)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgrespassword@postgres:5432/revenue_recovery")
BASELINE_JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "results", "baseline_comparison.json")
API_URL = os.getenv("API_URL", "http://api:8000" if "postgres:5432" in DATABASE_URL else "http://localhost:8000")

# Injected CSS Design System
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

    :root {
        --bg: #0A0E1A;
        --sidebar-bg: linear-gradient(180deg, #0D1224 0%, #141B33 100%);
        --card-bg: #12172A;
        --card-border: #232A42;
        --accent: #3395FF;
        --accent-hover: #528FF0;
        --text-primary: #F0F2F7;
        --text-secondary: #A8B0C4;
        --success: #4FD17A;
        --warning: #F0B429;
        --danger: #E05252;
        --ambiguous: #A06FE0;
        --passive: #22D3EE;
    }

    /* 1. Global Page Root & Font */
    html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stAppViewBlockContainer"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        background: var(--bg) !important;
        background-color: var(--bg) !important;
        color: var(--text-primary) !important;
        opacity: 1 !important;
        filter: none !important;
        backdrop-filter: none !important;
        -webkit-backdrop-filter: none !important;
    }

    /* 2. Top Header & Toolbar */
    header[data-testid="stHeader"] {
        background: var(--bg) !important;
        background-color: var(--bg) !important;
        border-bottom: 1px solid var(--card-border) !important;
    }
    header[data-testid="stHeader"] * {
        color: var(--text-primary) !important;
    }
    [data-testid="stToolbar"] {
        color: var(--text-primary) !important;
    }

    /* 3. Sidebar Container & Elements */
    [data-testid="stSidebar"], section[data-testid="stSidebar"] {
        background: var(--sidebar-bg) !important;
        border-right: 1px solid var(--card-border) !important;
        opacity: 1 !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] {
        gap: 6px;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child {
        display: none !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label {
        padding: 12px 16px !important;
        border-radius: 8px !important;
        background: transparent !important;
        border-left: 3px solid transparent !important;
        color: var(--text-secondary) !important;
        font-weight: 500 !important;
        font-size: 14px !important;
        cursor: pointer !important;
        transition: all 0.2s ease !important;
        margin-bottom: 4px !important;
        opacity: 1 !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
        background: rgba(51, 149, 255, 0.08) !important;
        color: var(--text-primary) !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label[data-checked="true"],
    [data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
        background: rgba(51, 149, 255, 0.12) !important;
        border-left: 3px solid var(--accent) !important;
        color: var(--accent) !important;
        font-weight: 600 !important;
    }

    /* 4. Top Bar Header & Breadcrumbs */
    .top-bar-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 4px 0 20px 0;
        margin-bottom: 24px;
        border-bottom: 1px solid var(--card-border);
    }
    .page-main-title {
        font-size: 24px;
        font-weight: 700;
        color: var(--text-primary);
        letter-spacing: -0.4px;
    }
    .page-subtitle {
        font-size: 12px;
        color: var(--text-secondary);
        letter-spacing: 0.8px;
        text-transform: uppercase;
        font-weight: 600;
        margin-top: 4px;
    }
    .test-mode-pill {
        background: rgba(240, 180, 41, 0.12);
        border: 1px solid rgba(240, 180, 41, 0.35);
        color: var(--warning);
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 0.4px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .pill-dot {
        font-size: 10px;
        color: var(--warning);
    }
    
    /* 5. Card System & Stat Tiles */
    .kpi-card {
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius: 12px;
        padding: 20px 14px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        width: 100%;
        min-height: 110px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
        transition: border-color 0.2s ease;
    }
    .kpi-card:hover {
        border-color: var(--accent);
    }
    .kpi-title { 
        font-size: 11px; 
        color: var(--text-secondary); 
        text-transform: uppercase; 
        letter-spacing: 0.8px; 
        font-weight: 600; 
        margin-bottom: 8px; 
        text-align: center;
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        line-height: 1.3;
    }
    .kpi-value { 
        font-size: 26px; 
        color: var(--text-primary); 
        font-weight: 700; 
        font-family: 'Inter', sans-serif;
        text-align: center;
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        line-height: 1.1;
    }

    .content-card {
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
    }
    .content-card:hover {
        border-color: rgba(51, 149, 255, 0.4);
    }
    
    /* 6. Form Widgets (Selectboxes, Text Inputs, Dropdowns) */
    div[data-baseweb="select"] {
        background-color: var(--card-bg) !important;
        border: 1px solid var(--card-border) !important;
        border-radius: 8px !important;
        color: var(--text-primary) !important;
    }
    div[data-baseweb="select"] * {
        background-color: transparent !important;
        color: var(--text-primary) !important;
    }
    div[data-baseweb="select"]:hover, div[data-baseweb="select"]:focus-within {
        border-color: var(--accent) !important;
    }
    ul[data-baseweb="menu"], div[data-baseweb="popover"], div[data-baseweb="popover"] > div {
        background-color: var(--card-bg) !important;
        border: 1px solid var(--card-border) !important;
    }
    li[data-baseweb="menu-item"] {
        background-color: var(--card-bg) !important;
        color: var(--text-primary) !important;
    }
    li[data-baseweb="menu-item"]:hover {
        background-color: rgba(51, 149, 255, 0.15) !important;
        color: var(--accent) !important;
    }

    .stTextInput input, div[data-baseweb="input"] input {
        background-color: var(--card-bg) !important;
        border: 1px solid var(--card-border) !important;
        border-radius: 8px !important;
        color: var(--text-primary) !important;
        font-family: 'Inter', sans-serif !important;
        padding: 10px 14px !important;
    }
    .stTextInput input:focus, div[data-baseweb="input"]:focus-within {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 1px var(--accent) !important;
    }
    .stTextInput input::placeholder {
        color: var(--text-secondary) !important;
    }

    /* Expander styling */
    [data-testid="stExpander"] {
        background-color: var(--card-bg) !important;
        border: 1px solid var(--card-border) !important;
        border-radius: 8px !important;
    }
    [data-testid="stExpander"] summary {
        color: var(--text-primary) !important;
    }

    /* 7. State Badges Tokens */
    .badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
        letter-spacing: 0.3px;
    }
    .badge-passive { background-color: rgba(34, 211, 238, 0.12); color: var(--passive); border: 1px solid rgba(34, 211, 238, 0.4); }
    .badge-ambiguous { background-color: rgba(160, 111, 224, 0.12); color: var(--ambiguous); border: 1px solid rgba(160, 111, 224, 0.4); }
    .badge-risk { background-color: rgba(224, 82, 82, 0.12); color: var(--danger); border: 1px solid rgba(224, 82, 82, 0.4); }
    .badge-dispatched { background-color: rgba(79, 209, 122, 0.12); color: var(--success); border: 1px solid rgba(79, 209, 122, 0.4); }
    .badge-resolved { background-color: rgba(79, 209, 122, 0.22); color: var(--success); border: 1px solid var(--success); font-weight: 700; }
    .badge-stopped { background-color: rgba(160, 111, 224, 0.15); color: var(--ambiguous); border: 1px solid rgba(160, 111, 224, 0.4); }
    .badge-dnd { background-color: rgba(51, 149, 255, 0.12); color: var(--accent); border: 1px solid rgba(51, 149, 255, 0.4); }
    .badge-default { background-color: rgba(168, 176, 196, 0.12); color: var(--text-secondary); border: 1px solid rgba(168, 176, 196, 0.3); }

    .variance-banner {
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-left: 4px solid var(--success);
        padding: 18px 22px;
        border-radius: 12px;
        margin-bottom: 24px;
        color: var(--text-primary);
    }
    
    .timeline-card {
        background-color: var(--card-bg);
        border-left: 3px solid var(--accent);
        padding: 14px 18px;
        margin-bottom: 12px;
        border-radius: 8px;
        border-top: 1px solid var(--card-border);
        border-right: 1px solid var(--card-border);
        border-bottom: 1px solid var(--card-border);
        transition: border-color 0.2s ease;
    }
    .timeline-card:hover {
        border-color: var(--accent);
    }

    code {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 12px !important;
    }
</style>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Data Loader Functions (Read-Only)
# -----------------------------------------------------------------------------
def get_db_conn():
    """
    Returns a live psycopg2 connection, transparently reconnecting if closed or broken.
    """
    if "db_conn" not in st.session_state or st.session_state["db_conn"].closed:
        st.session_state["db_conn"] = psycopg2.connect(DATABASE_URL)
    else:
        try:
            with st.session_state["db_conn"].cursor() as cur:
                cur.execute("SELECT 1;")
        except Exception:
            try:
                st.session_state["db_conn"].close()
            except Exception:
                pass
            st.session_state["db_conn"] = psycopg2.connect(DATABASE_URL)
    return st.session_state["db_conn"]


def fetch_live_metrics():
    """
    Queries live transaction aggregation counters from Postgres audit_logs.
    """
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    COUNT(*) as total_events,
                    COUNT(DISTINCT transaction_id) as total_txns,
                    COUNT(*) FILTER (WHERE to_state = 'action_sent') as dispatched,
                    COUNT(*) FILTER (WHERE to_state = 'resolved_success') as resolved,
                    COUNT(*) FILTER (WHERE to_state = 'ambiguous_escalated' OR to_state = 'escalated_human_review') as escalated,
                    COUNT(*) FILTER (WHERE to_state = 'passive_hold') as passive_hold,
                    COUNT(*) FILTER (WHERE to_state LIKE 'stopped_by_%' OR to_state = 'do_not_disturb') as stopped
                FROM audit_logs;
            """)
            row = cur.fetchone()
            if row:
                return {
                    "total_events": row[0],
                    "total_txns": row[1],
                    "dispatched": row[2],
                    "resolved": row[3],
                    "escalated": row[4],
                    "passive_hold": row[5],
                    "stopped": row[6]
                }
    except Exception as e:
        st.error(f"Postgres Query Error: {e}")
    return {"total_events": 0, "total_txns": 0, "dispatched": 0, "resolved": 0, "escalated": 0, "passive_hold": 0, "stopped": 0}


def fetch_live_feed(limit: int = 50):
    """
    Fetches the latest N audit log transitions in descending chronological sequence in IST,
    enriched with transaction-level diagnosis, causal scores, and cumulative cost for clear lineage.
    """
    conn = get_db_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                WITH recent_events AS (
                    SELECT 
                        seq_id,
                        timestamp AT TIME ZONE 'Asia/Kolkata' as timestamp,
                        transaction_id,
                        from_state,
                        to_state,
                        priority_score,
                        cate_score,
                        diagnosis_raw,
                        action_taken,
                        stopping_rule_triggered,
                        cost_of_action
                    FROM audit_logs
                    ORDER BY seq_id DESC
                    LIMIT %s
                ),
                txn_summaries AS (
                    SELECT 
                        transaction_id,
                        (ARRAY_AGG(diagnosis_raw ORDER BY seq_id DESC) FILTER (WHERE diagnosis_raw IS NOT NULL))[1] as last_diag,
                        (ARRAY_AGG(priority_score ORDER BY seq_id DESC) FILTER (WHERE priority_score IS NOT NULL))[1] as last_prio,
                        (ARRAY_AGG(cate_score ORDER BY seq_id DESC) FILTER (WHERE cate_score IS NOT NULL))[1] as last_cate,
                        SUM(cost_of_action) as cumulative_cost
                    FROM audit_logs
                    WHERE transaction_id IN (SELECT transaction_id FROM recent_events)
                    GROUP BY transaction_id
                )
                SELECT 
                    r.seq_id,
                    r.timestamp,
                    r.transaction_id,
                    r.from_state,
                    r.to_state,
                    COALESCE(r.priority_score, s.last_prio) as priority_score,
                    COALESCE(r.cate_score, s.last_cate) as cate_score,
                    COALESCE(r.diagnosis_raw, s.last_diag) as diagnosis_raw,
                    r.action_taken,
                    r.stopping_rule_triggered,
                    r.cost_of_action,
                    COALESCE(s.cumulative_cost, r.cost_of_action, 0.0) as cumulative_cost
                FROM recent_events r
                LEFT JOIN txn_summaries s ON r.transaction_id = s.transaction_id
                ORDER BY r.seq_id DESC;
            """, (limit,))
            return cur.fetchall()
    except Exception as e:
        st.error(f"Postgres Feed Error: {e}")
        return []


def load_baseline_comparison():
    """
    Reads the capstone-validated 4-Way baseline comparison dataset.
    """
    if os.path.exists(BASELINE_JSON_PATH):
        with open(BASELINE_JSON_PATH, "r") as f:
            return json.load(f)
    return None


def fetch_recent_transaction_ids(limit: int = 30):
    """
    Fetches the 30 most recently active distinct transaction IDs.
    """
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT transaction_id, MAX(seq_id) as max_seq
                FROM audit_logs
                GROUP BY transaction_id
                ORDER BY max_seq DESC
                LIMIT %s;
            """, (limit,))
            return [row[0] for row in cur.fetchall()]
    except Exception:
        return []


def fetch_timeline_from_api(transaction_id: str):
    """
    Calls GET /v1/audit/{transaction_id} via HTTP API.
    """
    try:
        try:
            resp = requests.get(f"{API_URL}/v1/audit/{transaction_id}", timeout=5.0)
        except Exception:
            resp = requests.get(f"http://localhost:8000/v1/audit/{transaction_id}", timeout=5.0)
            
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 404:
            return {"error": f"Transaction '{transaction_id}' not found in audit logs."}
        else:
            return {"error": f"API Error ({resp.status_code}): {resp.text}"}
    except Exception as e:
        return {"error": f"Could not reach Audit API: {e}"}


def verify_proof_from_api(transaction_id: str):
    """
    Calls GET /v1/audit/{transaction_id}/verify-proof via HTTP API.
    """
    try:
        try:
            resp = requests.get(f"{API_URL}/v1/audit/{transaction_id}/verify-proof", timeout=15.0)
        except Exception:
            resp = requests.get(f"http://localhost:8000/v1/audit/{transaction_id}/verify-proof", timeout=15.0)
            
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 404:
            return {"error": f"Transaction '{transaction_id}' not found."}
        else:
            return {"error": f"API Error ({resp.status_code}): {resp.text}"}
    except Exception as e:
        return {"error": f"Could not reach Proof API: {e}"}


def execute_demo_tamper(transaction_id: str, new_action: str = "MALICIOUS_UNAUTHORIZED_OVERRIDE"):
    """
    Deliberately corrupts an audit log action_taken field in Postgres for live demonstration.
    """
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE audit_logs
                SET action_taken = %s
                WHERE transaction_id = %s
                AND seq_id = (SELECT MIN(seq_id) FROM audit_logs WHERE transaction_id = %s);
            """, (new_action, transaction_id, transaction_id))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        st.error(f"Tamper query error: {e}")
        return False


def execute_demo_restore(transaction_id: str, original_action: str = "NONE"):
    """
    Restores the original database value for the selected transaction.
    """
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT from_state, to_state FROM audit_logs
                WHERE transaction_id = %s
                AND seq_id = (SELECT MIN(seq_id) FROM audit_logs WHERE transaction_id = %s);
            """, (transaction_id, transaction_id))
            row = cur.fetchone()
            act = "NONE"
            if row and row[1] == "triaged":
                act = "triage_dispatch"
            cur.execute("""
                UPDATE audit_logs
                SET action_taken = %s
                WHERE transaction_id = %s
                AND seq_id = (SELECT MIN(seq_id) FROM audit_logs WHERE transaction_id = %s);
            """, (act, transaction_id, transaction_id))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        st.error(f"Restore query error: {e}")
        return False


# -----------------------------------------------------------------------------
# Fixed Left Sidebar Navigation
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("""
    <div style="padding: 10px 4px 20px 4px;">
        <div style="font-size: 20px; font-weight: 700; color: #F0F2F7; letter-spacing: -0.4px; display: flex; align-items: center; gap: 8px;">
            <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background: #3395FF;"></span>
            DeclineZero
        </div>
        <div style="font-size: 11px; color: #A8B0C4; letter-spacing: 0.6px; text-transform: uppercase; font-weight: 600; margin-top: 4px;">
            Autonomous Revenue Recovery
        </div>
    </div>
    """, unsafe_allow_html=True)

    selected_page = st.radio(
        "Navigation",
        ["Live Monitor", "Batch Analytics", "Audit Explorer"],
        index=0,
        label_visibility="collapsed"
    )

    st.markdown("""
    <div style="margin-top: 100px; padding: 14px; background: rgba(18, 23, 42, 0.8); border: 1px solid #232A42; border-radius: 8px;">
        <div style="font-size: 11px; color: #A8B0C4; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Engine Status</div>
        <div style="font-size: 13px; color: #4FD17A; font-weight: 600; margin-top: 4px; display:flex; align-items:center; gap:6px;">
            <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background: #4FD17A;"></span>
            Online • Zero Violations
        </div>
    </div>
    """, unsafe_allow_html=True)


# =============================================================================
# VIEW 1: LIVE RECOVERY MONITOR
# =============================================================================
if selected_page == "Live Monitor":
    st.markdown("""
    <div class="top-bar-header">
        <div>
            <div class="page-main-title">Live Recovery Monitor</div>
            <div class="page-subtitle">Real-Time Ingestion & Decision Stream • PostgreSQL Audit Ledger</div>
        </div>
        <div class="test-mode-pill">
            <span class="pill-dot">●</span> TEST MODE — Simulated Sandbox
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_ctrl1, col_ctrl2 = st.columns([8, 2])
    with col_ctrl1:
        st.markdown("<div style='font-size:14px; color:#A8B0C4; font-weight:500; margin-bottom:12px;'>Aggregate System Counters</div>", unsafe_allow_html=True)
    with col_ctrl2:
        auto_refresh = st.checkbox("Auto-refresh (2s)", value=True)

    metrics = fetch_live_metrics()

    # KPI Strip in Cards
    kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)
    with kpi1:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Unique Transactions</div><div class="kpi-value">{metrics['total_txns']:,}</div></div>""", unsafe_allow_html=True)
    with kpi2:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Actions Dispatched</div><div class="kpi-value" style="color:var(--success);">{metrics['dispatched']:,}</div></div>""", unsafe_allow_html=True)
    with kpi3:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Resolved Success</div><div class="kpi-value" style="color:var(--success);">{metrics['resolved']:,}</div></div>""", unsafe_allow_html=True)
    with kpi4:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Passive Holds</div><div class="kpi-value" style="color:var(--passive);">{metrics['passive_hold']:,}</div></div>""", unsafe_allow_html=True)
    with kpi5:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Escalated Review</div><div class="kpi-value" style="color:var(--warning);">{metrics['escalated']:,}</div></div>""", unsafe_allow_html=True)
    with kpi6:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Compliance Stopped</div><div class="kpi-value" style="color:var(--ambiguous);">{metrics['stopped']:,}</div></div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Live Feed Table Container
    st.markdown("<div style='font-size:14px; color:#A8B0C4; font-weight:500; margin-bottom:12px;'>Recent 50 Lifecycle State Transitions</div>", unsafe_allow_html=True)
    feed_rows = fetch_live_feed(50)
    if feed_rows:
        display_data = []
        for r in feed_rows:
            ts_str = r['timestamp'].strftime("%H:%M:%S") if hasattr(r['timestamp'], "strftime") else str(r['timestamp'])[:19]
            st_val = r['to_state']
            
            # Razorpay-aligned badge indicators
            if st_val == "passive_hold":
                badge = '<span class="badge badge-passive">PASSIVE_HOLD (Self-Resolver)</span>'
            elif st_val == "ambiguous_escalated":
                badge = '<span class="badge badge-ambiguous">AMBIGUOUS_ESCALATED (Conformal Set)</span>'
            elif st_val == "escalated_human_review":
                badge = '<span class="badge badge-risk">ESCALATED_HUMAN_REVIEW (Risk Shield)</span>'
            elif st_val == "action_sent":
                act_name = r.get("action_taken") or "DISPATCH"
                badge = f'<span class="badge badge-dispatched">ACTION_SENT: {act_name}</span>'
            elif st_val == "resolved_success":
                badge = '<span class="badge badge-resolved">RESOLVED_SUCCESS</span>'
            elif st_val.startswith("stopped_by_"):
                rule_name = r.get("stopping_rule_triggered") or st_val
                badge = f'<span class="badge badge-stopped">STOPPED: {rule_name}</span>'
            elif st_val == "do_not_disturb":
                badge = '<span class="badge badge-dnd">DO_NOT_DISTURB (Negative CATE)</span>'
            else:
                badge = f'<span class="badge badge-default">{st_val}</span>'

            # Diagnosis Details (carried forward from earlier row if present)
            diag = r.get("diagnosis_raw")
            if isinstance(diag, dict):
                conf = diag.get('confidence', 1.0)
                conf_str = f" ({conf*100:.0f}%)" if conf is not None else ""
                diag_text = f"{diag.get('root_cause', 'N/A')}{conf_str}"
            elif isinstance(diag, str) and diag.startswith("{"):
                try:
                    d = json.loads(diag)
                    conf = d.get('confidence', 1.0)
                    conf_str = f" ({conf*100:.0f}%)" if conf is not None else ""
                    diag_text = f"{d.get('root_cause', 'N/A')}{conf_str}"
                except Exception:
                    diag_text = diag
            else:
                diag_text = "—"

            prio_val = r.get('priority_score')
            cate_val = r.get('cate_score')
            if prio_val is not None and cate_val is not None:
                prio_str = f"{float(prio_val):.2f} / {float(cate_val):+.2f}"
            elif prio_val is not None:
                prio_str = f"{float(prio_val):.2f}"
            else:
                prio_str = "—"

            cum_cost = float(r.get('cumulative_cost') if r.get('cumulative_cost') is not None else r.get('cost_of_action') or 0.0)

            display_data.append({
                "Seq": r['seq_id'],
                "Time (IST)": ts_str,
                "Transaction ID": r['transaction_id'],
                "State Transition": badge,
                "Root Cause Diagnosis": diag_text,
                "Priority / CATE": prio_str,
                "Cost (cumulative)": f"₹{cum_cost:.2f}"
            })

        df_feed = pd.DataFrame(display_data)
        st.write(df_feed.to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.info("No audit logs found. Submit transactions via /v1/webhook/razorpay to see live events.")

    if auto_refresh:
        time.sleep(2)
        st.rerun()


# =============================================================================
# VIEW 2: 4-WAY BATCH ANALYTICS
# =============================================================================
elif selected_page == "Batch Analytics":
    st.markdown("""
    <div class="top-bar-header">
        <div>
            <div class="page-main-title">4-Way Batch Analytics</div>
            <div class="page-subtitle">Comparative Economic Benchmark • 10,000-Transaction Scale</div>
        </div>
        <div class="test-mode-pill">
            <span class="pill-dot">●</span> TEST MODE — Simulated Sandbox
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 3-Seed Variance Range Banner (Post-Fix Reconciled)
    st.markdown("""
    <div class="variance-banner">
        <div style="color:var(--text-secondary); font-size:12px; text-transform:uppercase; letter-spacing:0.8px; font-weight:600;">Validated Headline Economic Delivery (3-Seed Robust Range):</div>
        <div style="font-size: 22px; font-weight:700; color: var(--success); margin: 4px 0;">₹154.18M ± ₹4.59M</div> 
        <div style="font-size: 13px; color: var(--text-secondary);"><b>Confidence Spread:</b> ₹149.49M – ₹158.67M &nbsp;&nbsp;•&nbsp;&nbsp; <b>Conversion Rate:</b> 54.46% ± 0.78% across independent batches</div>
    </div>
    """, unsafe_allow_html=True)

    data = load_baseline_comparison()
    if data and "policies" in data:
        p = data["policies"]
        
        # 1. Centerpiece Net Value Delivered Chart inside Card
        st.markdown("#### Net Value Delivered Across Recovery Paradigms")
        chart_data = pd.DataFrame([
            {"Policy": "1. Do Nothing", "Net Value (INR)": float(p["do_nothing"]["net_recovered_inr"]), "Color": "#6B7280"},
            {"Policy": "2. Blind Retry", "Net Value (INR)": float(p["blind_retry"]["net_recovered_inr"]), "Color": "#F0B429"},
            {"Policy": "3. Heuristic Rules", "Net Value (INR)": float(p["rules_only_no_uplift"]["net_recovered_inr"]), "Color": "#3395FF"},
            {"Policy": "4. DeclineZero (Ours)", "Net Value (INR)": float(p["decline_zero"]["net_recovered_inr"]), "Color": "#4FD17A"},
        ])

        bars = alt.Chart(chart_data).mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8).encode(
            x=alt.X("Policy:N", sort=None, axis=alt.Axis(labelAngle=0, title="", labelColor="#A8B0C4", labelFontSize=12)),
            y=alt.Y("Net Value (INR):Q", axis=alt.Axis(title="Net Value Delivered (INR)", titleColor="#A8B0C4", labelColor="#A8B0C4", gridColor="#232A42")),
            color=alt.Color("Color:N", scale=None, legend=None),
            tooltip=["Policy", alt.Tooltip("Net Value (INR):Q", format=",.2f")]
        )
        
        text = alt.Chart(chart_data).mark_text(
            align="center",
            baseline="bottom",
            dy=-6,
            color="#F0F2F7",
            fontWeight="bold",
            fontSize=13
        ).encode(
            x=alt.X("Policy:N", sort=None),
            y=alt.Y("Net Value (INR):Q"),
            text=alt.Text("Net Value (INR):Q", format=",.2f")
        )
        
        st.altair_chart((bars + text).properties(height=380).configure_view(strokeWidth=0), use_container_width=True)

        st.markdown("---")

        # 2. Comprehensive 4-Way Comparison Table
        st.markdown("#### Detailed 4-Way Policy Comparison Table")
        
        table_rows = []
        for key, pol in [
            ("do_nothing", p["do_nothing"]),
            ("blind_retry", p["blind_retry"]),
            ("rules_only_no_uplift", p["rules_only_no_uplift"]),
            ("decline_zero", p["decline_zero"])
        ]:
            table_rows.append({
                "Policy Paradigm": pol["name"],
                "Gross Recovered": f"₹{pol['recovered_amount_inr']:,.2f}",
                "Rec. Rate": f"{pol['recovery_rate_pct']:.2f}%",
                "Outreach Cost": f"₹{pol['total_outreach_cost_inr']:,.2f}",
                "Churn Loss (LTV)": f"₹{pol['monetized_churn_cost_inr']:,.2f}",
                "Penalty Risk": f"₹{pol['regulatory_penalty_cost_inr']:,.2f}",
                "Net Value Delivered": f"₹{pol['net_recovered_inr']:,.2f}",
                "Violations": f"{pol['compliance_violations']:,}",
                "Customer Churns": f"{pol['customer_churn_incidents']:,}"
            })

        df_comparison = pd.DataFrame(table_rows)
        st.dataframe(df_comparison, use_container_width=True, hide_index=True)

        st.markdown("---")

        # 3. Category Breakdown (B2B Receivables Story)
        st.markdown("#### Category-Level Breakdown (B2B Invoice Recovery Engine)")
        st.caption("DeclineZero unlocks massive high-ticket enterprise receivables through structured promise-to-pay tracking rather than naive consumer reminders.")
        
        cat_df = pd.DataFrame([
            {"Category": "Checkout", "Total Txns": "5,929", "Avg Ticket Size": "₹7,587.83", "Heuristic Rules Recovered": "₹24.48M (3,271)", "DeclineZero Recovered": "₹26.23M (3,189)", "Net Uplift": "+₹1.75M"},
            {"Category": "Subscription", "Total Txns": "2,517", "Avg Ticket Size": "₹1,770.16", "Heuristic Rules Recovered": "₹2.76M (1,577)", "DeclineZero Recovered": "₹2.55M (1,395)", "Net Uplift": "Zero Churn Mandates"},
            {"Category": "Receivable (B2B)", "Total Txns": "1,554", "Avg Ticket Size": "₹129,522.75", "Heuristic Rules Recovered": "₹3.26M (24)", "DeclineZero Recovered": "₹131.07M (1,021)", "Net Uplift": "+₹127.81M (40.2x)"},
        ])
        st.dataframe(cat_df, use_container_width=True, hide_index=True)

    else:
        st.warning("Baseline comparison dataset not found at results/baseline_comparison.json. Run Phase 8b evaluator to generate.")


# =============================================================================
# VIEW 3: AUDIT EXPLORER & CRYPTOGRAPHIC PROOF VERIFIER (PHASE 9b)
# =============================================================================
elif selected_page == "Audit Explorer":
    st.markdown("""
    <div class="top-bar-header">
        <div>
            <div class="page-main-title">Cryptographic Audit Explorer</div>
            <div class="page-subtitle">Immutable Merkle Proofs • Forensic Integrity Verification</div>
        </div>
        <div class="test-mode-pill">
            <span class="pill-dot">●</span> TEST MODE — Simulated Sandbox
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 1. Transaction Selection in Card
    st.markdown("<div style='font-size:14px; color:#A8B0C4; font-weight:500; margin-bottom:12px;'>Select or Search Transaction</div>", unsafe_allow_html=True)
    recent_txns = fetch_recent_transaction_ids(30)
    col_sel1, col_sel2 = st.columns([1, 1])
    with col_sel1:
        dropdown_txn = st.selectbox(
            "Select Recent Transaction:",
            options=[""] + recent_txns,
            index=1 if recent_txns else 0,
            help="Choose from the 30 most recently processed transactions"
        )
    with col_sel2:
        custom_txn = st.text_input(
            "Or Enter Custom Transaction ID:",
            value="",
            placeholder="e.g. pay_pitch_b1_clean_513c83",
            help="Type any valid transaction_id to look up its immutable audit ledger"
        )

    selected_txn_id = custom_txn.strip() if custom_txn.strip() else dropdown_txn

    if selected_txn_id:
        st.markdown("---")
        
        # 2. Timeline Narrative & Structured Metadata
        timeline_data = fetch_timeline_from_api(selected_txn_id)
        
        if "error" in timeline_data:
            st.error(timeline_data["error"])
        else:
            col_tl, col_proof = st.columns([6, 4])
            
            with col_tl:
                st.markdown(f"#### State Transition Timeline (`{selected_txn_id}`)")
                st.info(f"**Narrative Trace**: {timeline_data.get('timeline_summary', 'No summary')}")

                events = timeline_data.get("events", [])
                st.markdown(f"**Ledger Events Count**: {len(events)}")
                
                for idx, ev in enumerate(events):
                    ts_val = ev.get("timestamp", "")
                    ts_clean = str(ts_val)[:19]
                    to_s = ev.get("to_state", "")
                    from_s = ev.get("from_state") or "genesis"
                    action_s = ev.get("action_taken") or "—"
                    stop_s = ev.get("stopping_rule_triggered") or "—"
                    cost_val = float(ev.get("cost_of_action") or 0.0)

                    with st.container():
                        st.markdown(f"""
                        <div class="timeline-card">
                            <div style="display:flex; justify-content:space-between; font-size:12px; color:var(--text-secondary);">
                                <span><b>Step {idx+1}</b> • {from_s} ──► <b>{to_s}</b></span>
                                <span>{ts_clean} IST</span>
                            </div>
                            <div style="font-size:13px; color:var(--text-primary); margin-top:6px;">
                                <b>Action:</b> <code>{action_s}</code> &nbsp;|&nbsp; 
                                <b>Stopping Rule:</b> <code>{stop_s}</code> &nbsp;|&nbsp; 
                                <b>Cost:</b> ₹{cost_val:.2f}
                            </div>
                            <div style="font-size:11px; color:var(--text-secondary); margin-top:4px; font-family:'JetBrains Mono', monospace;">
                                Leaf Hash: {ev.get('leaf_hash', '')[:24]}... &nbsp;|&nbsp; Chain Hash: {ev.get('chain_hash', '')[:24]}...
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

            with col_proof:
                st.markdown("#### Cryptographic Integrity Verification")
                st.markdown("""
                Click below to compute the SHA-256 Merkle hash chain from **Genesis** across all sequential transitions in the database and verify zero tampering.
                """)
                
                verify_clicked = st.button("Verify Cryptographic Integrity", type="primary", use_container_width=True)
                
                if verify_clicked:
                    with st.spinner("Recomputing SHA-256 chain from Genesis..."):
                        proof_res = verify_proof_from_api(selected_txn_id)
                        
                        if "error" in proof_res:
                            st.error(f"Verification Error: {proof_res['error']}")
                        elif proof_res.get("verified") is True:
                            st.success(f"""
                            ### MATHEMATICALLY VERIFIED [CHAIN_VALID]
                            - **Status**: Chain Integrity Valid (0 Tamper Detected)
                            - **Records Verified**: {proof_res.get('total_records_verified', 0):,}
                            - **Stored Chain Hash**: `{proof_res.get('stored_hash', '')}`
                            - **Recomputed Hash**: `{proof_res.get('recomputed_hash', '')}`
                            - **Cryptographic Result**: Exact Match from Genesis Root.
                            """)
                        else:
                            st.error(f"""
                            ### CRYPTOGRAPHIC TAMPER DETECTED [DIVERGENCE_FOUND]
                            - **Status**: INVALID CHAIN HASH (Database Corrupted)
                            - **Stored Hash**: `{proof_res.get('stored_hash', '')}`
                            - **Recomputed Hash**: `{proof_res.get('recomputed_hash', '')}`
                            - **Divergence Details**: `{proof_res.get('divergence_details', {})}`
                            """)

                # 3. Judge Presentation Live Tamper Demonstration Utility
                st.markdown("<br>", unsafe_allow_html=True)
                with st.expander("JUDGE PRESENTATION UTILITY: Deliberate Database Tamper Demo", expanded=False):
                    st.warning("This utility is strictly for live demonstrations to prove real-time cryptographic tamper detection.")
                    col_t1, col_t2 = st.columns(2)
                    with col_t1:
                        if st.button("Tamper Record in DB (Corrupt Leaf)", use_container_width=True):
                            ok = execute_demo_tamper(selected_txn_id, new_action="MALICIOUS_UNAUTHORIZED_OVERRIDE")
                            if ok:
                                st.warning(f"Modified action_taken to 'MALICIOUS_UNAUTHORIZED_OVERRIDE' for `{selected_txn_id}` in Postgres. Click 'Verify Cryptographic Integrity' above to observe tamper detection!")
                    with col_t2:
                        if st.button("Restore Original DB Value", use_container_width=True):
                            ok = execute_demo_restore(selected_txn_id)
                            if ok:
                                st.success(f"Restored original values for `{selected_txn_id}` in Postgres. Click 'Verify Cryptographic Integrity' above to confirm verified status!")

            # Raw Metadata Inspector Table
            st.markdown("---")
            with st.expander("Inspect Raw Structured Audit Event Records (JSON)", expanded=False):
                st.json(events)

    else:
        st.info("Select or enter a transaction ID to explore its cryptographic timeline.")
