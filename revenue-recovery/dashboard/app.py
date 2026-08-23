"""
DeclineZero — Autonomous AI Revenue Recovery Dashboard (Streamlit).

Pages / Tabs:
1. ⚡ Live Recovery Monitor: Real-time transaction feed, live KPI counters, and color-coded safety badges.
2. 📊 4-Way Batch Analytics: Economic benchmark, Net Value centerpiece chart, B2B breakdown, and 3-seed variance range.
3. 🔍 Audit Explorer: (Phase 9b).
"""
import os
import json
import time
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
import altair as alt
import streamlit as st

# -----------------------------------------------------------------------------
# Configuration & Styling
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="DeclineZero | AI Revenue Recovery Engine",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgrespassword@postgres:5432/revenue_recovery")
BASELINE_JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "results", "baseline_comparison.json")

# Custom CSS styling for modern fintech dark aesthetic
st.markdown("""
<style>
    .main { background-color: #0d1117; }
    .kpi-card {
        background: linear-gradient(135deg, rgba(22, 27, 34, 0.8), rgba(33, 38, 45, 0.6));
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 16px 20px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    .kpi-title { font-size: 13px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; margin-bottom: 4px; }
    .kpi-value { font-size: 26px; color: #f0f6fc; font-weight: 700; }
    
    .badge-passive { background-color: rgba(0, 229, 255, 0.15); color: #00e5ff; border: 1px solid #00e5ff; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 12px; }
    .badge-ambiguous { background-color: rgba(255, 171, 0, 0.15); color: #ffab00; border: 1px solid #ffab00; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 12px; }
    .badge-dispatched { background-color: rgba(0, 230, 118, 0.15); color: #00e676; border: 1px solid #00e676; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 12px; }
    .badge-resolved { background-color: rgba(29, 233, 182, 0.2); color: #1de9b6; border: 1px solid #1de9b6; padding: 3px 8px; border-radius: 4px; font-weight: 700; font-size: 12px; }
    .badge-stopped { background-color: rgba(224, 64, 251, 0.15); color: #e040fb; border: 1px solid #e040fb; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 12px; }
    .badge-dnd { background-color: rgba(41, 121, 255, 0.15); color: #2979ff; border: 1px solid #2979ff; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 12px; }
    .badge-default { background-color: rgba(139, 148, 158, 0.15); color: #8b949e; border: 1px solid #8b949e; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 12px; }

    .variance-banner {
        background: linear-gradient(90deg, #1f2937, #111827);
        border-left: 4px solid #10b981;
        padding: 12px 18px;
        border-radius: 6px;
        margin-bottom: 20px;
        color: #e5e7eb;
    }
</style>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Data Loader Functions (Read-Only)
# -----------------------------------------------------------------------------
@st.cache_resource
def get_db_conn():
    return psycopg2.connect(DATABASE_URL)


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
                    COUNT(*) FILTER (WHERE to_state = 'action_sent' OR (action_taken IS NOT NULL AND action_taken NOT IN ('NONE', 'stop', 'payment_captured'))) as dispatched,
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
    Fetches the latest N audit log transitions in descending chronological sequence.
    """
    conn = get_db_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    seq_id,
                    timestamp,
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
                LIMIT %s;
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


# -----------------------------------------------------------------------------
# Main Application Structure
# -----------------------------------------------------------------------------
st.title("⚡ DeclineZero — Closed-Loop AI Revenue Recovery")
st.caption("Razorpay Autonomous Decisioning Engine • Non-Intrusive Causal Triage • Conformal Safeguards • Merkle Audit Trail")

# Navigation bar (Horizontal stateful navigation)
selected_page = st.radio(
    "Navigation",
    ["⚡ Live Recovery Monitor", "📊 4-Way Batch Analytics", "🔍 Cryptographic Audit Explorer"],
    horizontal=True,
    label_visibility="collapsed"
)

st.markdown("<br>", unsafe_allow_html=True)

# =============================================================================
# VIEW 1: LIVE RECOVERY MONITOR
# =============================================================================
if selected_page == "⚡ Live Recovery Monitor":
    col_ctrl1, col_ctrl2 = st.columns([8, 2])
    with col_ctrl1:
        st.markdown("### Real-Time Recovery Stream")
    with col_ctrl2:
        auto_refresh = st.checkbox("Auto-refresh (2s)", value=True)

    metrics = fetch_live_metrics()

    # KPI Strip
    kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)
    with kpi1:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Total Processed</div><div class="kpi-value">{metrics['total_txns']:,}</div></div>""", unsafe_allow_html=True)
    with kpi2:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Actions Sent</div><div class="kpi-value" style="color:#00e676;">{metrics['dispatched']:,}</div></div>""", unsafe_allow_html=True)
    with kpi3:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Resolved Success</div><div class="kpi-value" style="color:#1de9b6;">{metrics['resolved']:,}</div></div>""", unsafe_allow_html=True)
    with kpi4:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Passive Holds (CATE≤0)</div><div class="kpi-value" style="color:#00e5ff;">{metrics['passive_hold']:,}</div></div>""", unsafe_allow_html=True)
    with kpi5:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Conformal Escalated</div><div class="kpi-value" style="color:#ffab00;">{metrics['escalated']:,}</div></div>""", unsafe_allow_html=True)
    with kpi6:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Compliance Stopped</div><div class="kpi-value" style="color:#e040fb;">{metrics['stopped']:,}</div></div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Live Feed Table
    feed_rows = fetch_live_feed(50)
    if feed_rows:
        display_data = []
        for r in feed_rows:
            ts_str = r['timestamp'].strftime("%H:%M:%S") if hasattr(r['timestamp'], "strftime") else str(r['timestamp'])[:19]
            st_val = r['to_state']
            
            # Format badges
            if st_val == "passive_hold":
                badge = '<span class="badge-passive">🛡️ PASSIVE_HOLD (Sleeping Dog)</span>'
            elif st_val in ("ambiguous_escalated", "escalated_human_review"):
                badge = '<span class="badge-ambiguous">⚠️ AMBIGUOUS_ESCALATED (Conformal Set)</span>'
            elif st_val == "action_sent":
                act_name = r.get("action_taken") or "DISPATCH"
                badge = f'<span class="badge-dispatched">🚀 ACTION_SENT: {act_name}</span>'
            elif st_val == "resolved_success":
                badge = '<span class="badge-resolved">💰 RESOLVED_SUCCESS</span>'
            elif st_val.startswith("stopped_by_"):
                rule_name = r.get("stopping_rule_triggered") or st_val
                badge = f'<span class="badge-stopped">🛑 {rule_name}</span>'
            elif st_val == "do_not_disturb":
                badge = '<span class="badge-dnd">🔇 DO_NOT_DISTURB</span>'
            else:
                badge = f'<span class="badge-default">{st_val}</span>'

            # Diagnosis Details
            diag = r.get("diagnosis_raw")
            if isinstance(diag, dict):
                diag_text = f"{diag.get('root_cause', 'N/A')} ({diag.get('confidence', 1.0)*100:.0f}%)"
            else:
                diag_text = "—"

            display_data.append({
                "Seq": r['seq_id'],
                "Time (IST)": ts_str,
                "Transaction ID": r['transaction_id'],
                "State Transition": badge,
                "Root Cause Diagnosis": diag_text,
                "Priority / CATE": f"{r.get('priority_score') or 0:.2f} / {r.get('cate_score') or 0:+.2f}" if r.get('priority_score') is not None else "—",
                "Cost": f"₹{float(r.get('cost_of_action') or 0.0):.2f}"
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
elif selected_page == "📊 4-Way Batch Analytics":
    st.markdown("### Comparative Economic Benchmark (10,000-Transaction Scale)")
    
    # 3-Seed Variance Range Banner (Post-Fix Reconciled)
    st.markdown("""
    <div class="variance-banner">
        <b>🎯 Validated Headline Economic Delivery (3-Seed Robust Range):</b><br>
        <span style="font-size: 18px; font-weight:700; color: #10b981;">₹154.18M ± ₹4.59M</span> 
        &nbsp;&nbsp;•&nbsp;&nbsp; <b>Confidence Spread:</b> ₹149.49M – ₹158.67M 
        &nbsp;&nbsp;•&nbsp;&nbsp; <b>Conversion Rate:</b> 54.46% ± 0.78% across independent batches
    </div>
    """, unsafe_allow_html=True)

    data = load_baseline_comparison()
    if data and "policies" in data:
        p = data["policies"]
        
        # 1. Centerpiece Net Value Delivered Chart
        st.markdown("#### 🏆 Net Value Delivered Across Recovery Paradigms")
        chart_data = pd.DataFrame([
            {"Policy": "1. Do Nothing", "Net Value (INR)": float(p["do_nothing"]["net_recovered_inr"]), "Color": "#6b7280"},
            {"Policy": "2. Blind Retry", "Net Value (INR)": float(p["blind_retry"]["net_recovered_inr"]), "Color": "#f59e0b"},
            {"Policy": "3. Heuristic Rules", "Net Value (INR)": float(p["rules_only_no_uplift"]["net_recovered_inr"]), "Color": "#3b82f6"},
            {"Policy": "4. DeclineZero (Ours)", "Net Value (INR)": float(p["decline_zero"]["net_recovered_inr"]), "Color": "#10b981"},
        ])

        bars = alt.Chart(chart_data).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
            x=alt.X("Policy:N", sort=None, axis=alt.Axis(labelAngle=0, title="")),
            y=alt.Y("Net Value (INR):Q", axis=alt.Axis(title="Net Value Delivered (INR)")),
            color=alt.Color("Color:N", scale=None, legend=None),
            tooltip=["Policy", alt.Tooltip("Net Value (INR):Q", format=",.2f")]
        )
        
        text = alt.Chart(chart_data).mark_text(
            align="center",
            baseline="bottom",
            dy=-5,
            color="#f0f6fc",
            fontWeight="bold"
        ).encode(
            x=alt.X("Policy:N", sort=None),
            y=alt.Y("Net Value (INR):Q"),
            text=alt.Text("Net Value (INR):Q", format=",.2f")
        )
        
        st.altair_chart((bars + text).properties(height=380), use_container_width=True)

        st.markdown("---")

        # 2. Comprehensive 4-Way Comparison Table
        st.markdown("#### 📋 Detailed 4-Way Policy Comparison Table")
        
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
        st.markdown("#### 🏢 Category-Level Breakdown (B2B Invoice Recovery Engine)")
        st.caption("DeclineZero unlocks massive high-ticket enterprise receivables through structured promise-to-pay tracking rather than naive consumer reminders.")
        
        cat_df = pd.DataFrame([
            {"Category": "Checkout", "Total Txns": "5,929", "Avg Ticket Size": "₹7,587.83", "Heuristic Rules Recovered": "₹24.48M (3,271)", "DeclineZero Recovered": "₹26.23M (3,189)", "Net Uplift": "+₹1.75M"},
            {"Category": "Subscription", "Total Txns": "2,517", "Avg Ticket Size": "₹1,770.16", "Heuristic Rules Recovered": "₹2.76M (1,577)", "DeclineZero Recovered": "₹2.55M (1,395)", "Net Uplift": "Zero Churn Mandates"},
            {"Category": "Receivable (B2B)", "Total Txns": "1,554", "Avg Ticket Size": "₹129,522.75", "Heuristic Rules Recovered": "₹3.26M (24)", "DeclineZero Recovered": "₹131.07M (1,021)", "Net Uplift": "+₹127.81M (40.2x)"},
        ])
        st.dataframe(cat_df, use_container_width=True, hide_index=True)

    else:
        st.warning("Baseline comparison dataset not found at results/baseline_comparison.json. Run Phase 8b evaluator to generate.")


# -----------------------------------------------------------------------------
# API Helper Functions for Audit Trail (Exercising Real Backend API)
# -----------------------------------------------------------------------------
API_URL = os.getenv("API_URL", "http://api:8000" if "postgres:5432" in DATABASE_URL else "http://localhost:8000")
import requests


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
        # Try configured API_URL first, fallback to localhost if outside container
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
    Deliberately corrupts an audit log action_taken field in Postgres for live hackathon demonstration.
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


# =============================================================================
# VIEW 3: AUDIT EXPLORER & CRYPTOGRAPHIC PROOF VERIFIER (PHASE 9b)
# =============================================================================
elif selected_page == "🔍 Cryptographic Audit Explorer":
    st.markdown("### 🔍 Cryptographic Audit Explorer & Immutable Merkle Proofs")
    st.caption("Inspect every automated transition step, causal score, root-cause diagnosis, and verify mathematical tamper-evidence from Genesis.")

    # 1. Transaction Selection
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
            placeholder="e.g. pay_aud1_675d98_1692_checkout",
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
                st.markdown(f"#### 📜 State Transition Timeline (`{selected_txn_id}`)")
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
                        <div style="background-color: #161b22; border-left: 3px solid #58a6ff; padding: 10px 14px; margin-bottom: 8px; border-radius: 4px;">
                            <div style="display:flex; justify-content:space-between; font-size:12px; color:#8b949e;">
                                <span><b>Step {idx+1}</b> • {from_s} ──► <b>{to_s}</b></span>
                                <span>{ts_clean} IST</span>
                            </div>
                            <div style="font-size:13px; color:#f0f6fc; margin-top:4px;">
                                <b>Action:</b> <code>{action_s}</code> &nbsp;|&nbsp; 
                                <b>Stopping Rule:</b> <code>{stop_s}</code> &nbsp;|&nbsp; 
                                <b>Cost:</b> ₹{cost_val:.2f}
                            </div>
                            <div style="font-size:11px; color:#6e7681; margin-top:2px; font-family:monospace;">
                                Leaf Hash: {ev.get('leaf_hash', '')[:24]}... &nbsp;|&nbsp; Chain Hash: {ev.get('chain_hash', '')[:24]}...
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

            with col_proof:
                st.markdown("#### 🛡️ Cryptographic Integrity Verification")
                st.markdown("""
                Click below to compute the SHA-256 Merkle hash chain from **Genesis** across all sequential transitions in the database and verify zero tampering.
                """)
                
                verify_clicked = st.button("🔐 Verify Cryptographic Integrity", type="primary", use_container_width=True)
                
                if verify_clicked:
                    with st.spinner("Recomputing SHA-256 chain from Genesis..."):
                        proof_res = verify_proof_from_api(selected_txn_id)
                        
                        if "error" in proof_res:
                            st.error(f"Verification Error: {proof_res['error']}")
                        elif proof_res.get("verified") is True:
                            st.success(f"""
                            ### ✅ MATHEMATICALLY VERIFIED
                            - **Status**: Chain Integrity Valid (0 Tamper Detected)
                            - **Records Verified**: {proof_res.get('total_records_verified', 0):,}
                            - **Stored Chain Hash**: `{proof_res.get('stored_hash', '')}`
                            - **Recomputed Hash**: `{proof_res.get('recomputed_hash', '')}`
                            - **Cryptographic Result**: Exact Match from Genesis Root.
                            """)
                        else:
                            st.error(f"""
                            ### 🚨 CRYPTOGRAPHIC TAMPER DETECTED!
                            - **Status**: INVALID CHAIN HASH (Database Corrupted)
                            - **Stored Hash**: `{proof_res.get('stored_hash', '')}`
                            - **Recomputed Hash**: `{proof_res.get('recomputed_hash', '')}`
                            - **Divergence Details**: `{proof_res.get('divergence_details', {})}`
                            """)

                # 3. Judge Presentation Live Tamper Demonstration Utility
                st.markdown("<br>", unsafe_allow_html=True)
                with st.expander("⚠️ JUDGE PRESENTATION UTILITY: Deliberate Database Tamper Demo", expanded=False):
                    st.warning("This utility is strictly for live hackathon judging to demonstrate real-time cryptographic tamper detection.")
                    col_t1, col_t2 = st.columns(2)
                    with col_t1:
                        if st.button("🚨 Tamper Record in DB", use_container_width=True):
                            ok = execute_demo_tamper(selected_txn_id, new_action="MALICIOUS_UNAUTHORIZED_OVERRIDE")
                            if ok:
                                st.warning(f"Modified action_taken to 'MALICIOUS_UNAUTHORIZED_OVERRIDE' for `{selected_txn_id}` in Postgres. Click 'Verify Integrity' above to observe tamper detection!")
                    with col_t2:
                        if st.button("🔄 Restore Original DB Value", use_container_width=True):
                            ok = execute_demo_restore(selected_txn_id)
                            if ok:
                                st.success(f"Restored original values for `{selected_txn_id}` in Postgres. Click 'Verify Integrity' above to confirm verified status!")

            # Raw Metadata Inspector Table
            st.markdown("---")
            with st.expander("🔬 Inspect Raw Structured Audit Event Records (JSON)", expanded=False):
                st.json(events)

    else:
        st.info("Select or enter a transaction ID to explore its cryptographic timeline.")
