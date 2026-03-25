"""
Snowflake Cost Monitor — Main Dashboard
========================================
Entry point for the multi-page Streamlit app.
Displays an account-level cost overview with drill-down links.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from utils.snowflake_connector import run_query, test_connection, format_credits
from utils.queries import (
    OVERVIEW_TOTAL_CREDITS,
    OVERVIEW_DAILY_CREDITS,
    OVERVIEW_CREDITS_BY_SERVICE,
    OVERVIEW_STORAGE_TOTAL,
    RESOURCE_MONITORS,
    date_filter,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Snowflake Cost Monitor",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image(
        "https://www.snowflake.com/wp-content/themes/snowflake/assets/img/brand-guidelines/logo-sno-blue-example.svg",
        width=180,
    )
    st.title("Snowflake Cost Monitor")
    st.markdown("---")

    days = st.selectbox(
        "Look-back period",
        options=[7, 14, 30, 60, 90],
        index=2,
        format_func=lambda d: f"Last {d} days",
    )

    credit_rate = st.number_input(
        "Credit rate (USD)",
        min_value=0.5,
        max_value=50.0,
        value=3.0,
        step=0.25,
        help="Estimated USD cost per Snowflake credit (varies by edition & region).",
    )

    st.markdown("---")
    st.caption("Data source: SNOWFLAKE.ACCOUNT_USAGE")
    st.caption("Latency: up to 3 hours")

    # Connection status
    if st.button("Test Connection", use_container_width=True):
        with st.spinner("Connecting…"):
            ok, msg = test_connection()
        if ok:
            st.success(msg)
        else:
            st.error(msg)

# ── Helpers ───────────────────────────────────────────────────────────────────
DF = date_filter(days)

def est_cost(credits: float) -> str:
    return f"${credits * credit_rate:,.0f}"


def metric_card(col, label: str, credits: float, delta_credits: float | None = None):
    col.metric(
        label=label,
        value=f"{credits:,.1f} credits",
        delta=f"{delta_credits:+,.1f}" if delta_credits is not None else None,
        delta_color="inverse",
    )
    col.caption(f"≈ {est_cost(credits)}")


# ── Header ────────────────────────────────────────────────────────────────────
st.title("❄️ Snowflake Cost Monitor")
st.caption(f"Overview for the last **{days} days** · Estimated at **${credit_rate:.2f}**/credit")
st.markdown("---")

# ── KPI row ───────────────────────────────────────────────────────────────────
with st.spinner("Loading totals…"):
    try:
        totals_df = run_query(OVERVIEW_TOTAL_CREDITS.format(date_filter=DF))
        storage_df = run_query(OVERVIEW_STORAGE_TOTAL.format(date_filter=DF))
    except Exception as e:
        st.error(f"Query failed: {e}")
        st.info(
            "Make sure your Snowflake credentials are configured in `.streamlit/secrets.toml` "
            "or as environment variables. See the README for details."
        )
        st.stop()

if totals_df.empty:
    st.warning("No metering data found for this period.")
    st.stop()

# Normalise column names to lowercase
totals_df.columns = [c.lower() for c in totals_df.columns]
storage_df.columns = [c.lower() for c in storage_df.columns]

total_credits    = float(totals_df["total_credits"].iloc[0] or 0)
compute_credits  = float(totals_df["compute_credits"].iloc[0] or 0)
cloud_credits    = float(totals_df["cloud_svc_credits"].iloc[0] or 0)
avg_total_tb     = float(storage_df["avg_total_tb"].iloc[0] or 0)

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Total Credits Consumed", f"{total_credits:,.1f}", help="All service types combined")
    st.caption(f"≈ {est_cost(total_credits)}")
with c2:
    st.metric("Compute Credits", f"{compute_credits:,.1f}", help="Virtual warehouse compute")
    st.caption(f"≈ {est_cost(compute_credits)}")
with c3:
    st.metric("Cloud Services Credits", f"{cloud_credits:,.1f}", help="Metadata, auth, query compilation")
    st.caption(f"≈ {est_cost(cloud_credits)}")
with c4:
    storage_cost = avg_total_tb * 23 * (days / 30)  # ~$23/TB/month
    st.metric("Avg Storage", f"{avg_total_tb:,.2f} TB", help="Avg daily total storage (DB + Stage + Failsafe)")
    st.caption(f"≈ ${storage_cost:,.0f} est.")

st.markdown("---")

# ── Daily credit trend ────────────────────────────────────────────────────────
st.subheader("Daily Credit Consumption")

with st.spinner("Loading daily trend…"):
    daily_df = run_query(OVERVIEW_DAILY_CREDITS.format(date_filter=DF))

if not daily_df.empty:
    daily_df.columns = [c.lower() for c in daily_df.columns]
    daily_df["usage_date"] = pd.to_datetime(daily_df["usage_date"])

    fig = px.bar(
        daily_df,
        x="usage_date",
        y="total_credits",
        color="service_type",
        title="Credits by Service Type (Daily)",
        labels={"usage_date": "Date", "total_credits": "Credits", "service_type": "Service"},
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Service type breakdown ────────────────────────────────────────────────────
col_pie, col_tbl = st.columns([1, 1])

with st.spinner("Loading service breakdown…"):
    svc_df = run_query(OVERVIEW_CREDITS_BY_SERVICE.format(date_filter=DF))

if not svc_df.empty:
    svc_df.columns = [c.lower() for c in svc_df.columns]

    with col_pie:
        st.subheader("Credits by Service Type")
        fig2 = px.pie(
            svc_df,
            names="service_type",
            values="total_credits",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Pastel,
        )
        fig2.update_layout(
            showlegend=True,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig2, use_container_width=True)

    with col_tbl:
        st.subheader("Credit Summary by Service")
        display_df = svc_df[["service_type", "compute_credits", "cloud_svc_credits", "total_credits"]].copy()
        display_df["est_cost_usd"] = (display_df["total_credits"] * credit_rate).map("${:,.0f}".format)
        display_df.columns = ["Service Type", "Compute Credits", "Cloud Svc Credits", "Total Credits", "Est. Cost (USD)"]
        st.dataframe(display_df, use_container_width=True, hide_index=True)

# ── Resource Monitors ─────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Resource Monitors")

with st.spinner("Loading resource monitors…"):
    rm_df = run_query(RESOURCE_MONITORS)

if not rm_df.empty:
    rm_df.columns = [c.lower() for c in rm_df.columns]

    # Color-code usage percentage
    def color_usage(val):
        if val is None:
            return ""
        val = float(val)
        if val >= 90:
            return "background-color: #8B0000; color: white"
        elif val >= 75:
            return "background-color: #FF8C00; color: black"
        elif val >= 50:
            return "background-color: #DAA520; color: black"
        return ""

    display_cols = ["monitor_name", "frequency", "credit_quota", "credits_used", "usage_pct", "suspend_at", "owner"]
    avail_cols = [c for c in display_cols if c in rm_df.columns]
    styled = rm_df[avail_cols].style.applymap(color_usage, subset=["usage_pct"] if "usage_pct" in avail_cols else [])
    st.dataframe(styled, use_container_width=True, hide_index=True)
else:
    st.info("No resource monitors found.")

# ── Quick navigation ──────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Drill-Down Views")

nav_cols = st.columns(5)
pages = [
    ("💻 Compute", "pages/1_Compute_Costs.py", "Warehouse credit usage and trends"),
    ("🗄️ Storage", "pages/2_Storage_Costs.py", "DB, Stage, Failsafe & Time Travel"),
    ("🔍 Queries", "pages/3_Query_Analysis.py", "Expensive queries, user costs"),
    ("⚙️ Serverless", "pages/4_Serverless_Cloud_Services.py", "Pipes, Tasks, MV, Clustering"),
    ("🏭 Efficiency", "pages/5_Warehouse_Efficiency.py", "Idle time, queuing, sizing"),
]
for col, (title, _, desc) in zip(nav_cols, pages):
    col.info(f"**{title}**\n\n{desc}")

st.caption("Use the sidebar to navigate between pages →")
