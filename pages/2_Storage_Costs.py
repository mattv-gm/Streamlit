"""
Storage Costs Page
==================
Database storage, stage storage, failsafe, time-travel, and per-table breakdown.
Snowflake charges ~$23/TB/month for storage (on-demand) or ~$40/TB for capacity.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from utils.snowflake_connector import run_query
from utils.queries import (
    STORAGE_DAILY,
    STORAGE_BY_DATABASE,
    STORAGE_BY_TABLE_TOP,
    STORAGE_STAGE_USAGE,
    date_filter,
)

st.set_page_config(page_title="Storage Costs | Snowflake Monitor", page_icon="🗄️", layout="wide")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🗄️ Storage Costs")
    days = st.selectbox("Look-back period", [7, 14, 30, 60, 90], index=2,
                        format_func=lambda d: f"Last {d} days")
    storage_rate = st.number_input(
        "Storage rate (USD/TB/month)",
        min_value=1.0, max_value=100.0, value=23.0, step=1.0,
        help="On-demand pricing ~$23/TB/month. Capacity pricing ~$40/TB/month."
    )
    st.markdown("---")
    st.caption("Source: STORAGE_USAGE, TABLE_STORAGE_METRICS")

DF = date_filter(days, col="usage_date")

st.title("🗄️ Storage Costs")
st.caption(f"Last {days} days · ${storage_rate:.0f}/TB/month storage rate")
st.markdown("---")

# ── Daily storage trend ───────────────────────────────────────────────────────
st.subheader("Storage Trend Over Time")

with st.spinner("Loading storage trend…"):
    daily_df = run_query(STORAGE_DAILY.format(date_filter=DF))

if daily_df.empty:
    st.warning("No storage data found for this period.")
    st.stop()

daily_df.columns = [c.lower() for c in daily_df.columns]
daily_df["usage_date"] = pd.to_datetime(daily_df["usage_date"])

# KPI cards from most recent day
latest = daily_df.iloc[0]
c1, c2, c3, c4 = st.columns(4)
db_gb   = float(latest.get("database_gb", 0) or 0)
st_gb   = float(latest.get("stage_gb", 0) or 0)
fs_gb   = float(latest.get("failsafe_gb", 0) or 0)
tot_gb  = float(latest.get("total_gb", 0) or 0)
monthly_cost = tot_gb / 1024 * storage_rate

c1.metric("Database Storage", f"{db_gb:,.1f} GB")
c1.caption(f"≈ ${db_gb/1024*storage_rate:,.0f}/mo")
c2.metric("Stage Storage", f"{st_gb:,.1f} GB")
c2.caption(f"≈ ${st_gb/1024*storage_rate:,.0f}/mo")
c3.metric("Failsafe Storage", f"{fs_gb:,.1f} GB")
c3.caption(f"≈ ${fs_gb/1024*storage_rate:,.0f}/mo")
c4.metric("Total Storage", f"{tot_gb:,.1f} GB")
c4.caption(f"≈ ${monthly_cost:,.0f}/mo")

# Stacked area chart
fig = go.Figure()
for col, label, color in [
    ("database_gb", "Database", "#29B5E8"),
    ("stage_gb", "Stage", "#44D7B6"),
    ("failsafe_gb", "Failsafe", "#FF6B6B"),
]:
    fig.add_trace(go.Scatter(
        x=daily_df["usage_date"], y=daily_df[col],
        name=label, mode="lines",
        stackgroup="one",
        line=dict(color=color, width=1),
        fillcolor=color.replace(")", ",0.5)").replace("rgb", "rgba") if color.startswith("rgb") else color,
    ))
fig.update_layout(
    title="Storage by Type (GB)", xaxis_title="Date", yaxis_title="GB",
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    xaxis=dict(showgrid=False),
    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ── Per-database breakdown ────────────────────────────────────────────────────
st.subheader("Storage by Database")

with st.spinner("Loading per-database storage…"):
    db_df = run_query(STORAGE_BY_DATABASE)

if not db_df.empty:
    db_df.columns = [c.lower() for c in db_df.columns]
    db_df["monthly_cost_usd"] = db_df["total_gb"] / 1024 * storage_rate

    col_chart, col_tbl = st.columns([2, 2])

    with col_chart:
        fig2 = px.treemap(
            db_df.head(30),
            path=["database_name"],
            values="total_gb",
            color="total_gb",
            color_continuous_scale="Blues",
            title="Storage Treemap by Database",
        )
        fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)

    with col_tbl:
        display = db_df[["database_name", "active_gb", "time_travel_gb",
                          "failsafe_gb", "clone_gb", "total_gb", "monthly_cost_usd"]].copy()
        display["monthly_cost_usd"] = display["monthly_cost_usd"].map("${:,.0f}".format)
        display.columns = ["Database", "Active GB", "Time Travel GB",
                           "Failsafe GB", "Clone GB", "Total GB", "Est. Monthly Cost"]
        st.dataframe(display, use_container_width=True, hide_index=True)

st.markdown("---")

# ── Storage composition pie ───────────────────────────────────────────────────
st.subheader("Storage Cost Composition")

col_left, col_right = st.columns(2)

with col_left:
    if not db_df.empty:
        totals = {
            "Active": db_df["active_gb"].sum(),
            "Time Travel": db_df["time_travel_gb"].sum(),
            "Failsafe": db_df["failsafe_gb"].sum(),
            "Clone": db_df["clone_gb"].sum(),
        }
        pie_df = pd.DataFrame(list(totals.items()), columns=["Type", "GB"])
        fig3 = px.pie(pie_df, names="Type", values="GB", hole=0.4,
                      title="Storage by Layer (All Databases)",
                      color_discrete_sequence=px.colors.qualitative.Pastel)
        fig3.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig3, use_container_width=True)

with col_right:
    st.markdown("#### Storage Pricing Guide")
    st.info(
        "**Active Storage** – tables currently in use.\n\n"
        "**Time Travel** – data retained for point-in-time queries (1–90 days).\n\n"
        "**Failsafe** – 7-day disaster recovery layer (charged after time-travel expires).\n\n"
        "**Clones** – zero-copy clones only charge for new data written.\n\n"
        f"All billed at **${storage_rate}/TB/month** (on-demand rate)."
    )
    st.markdown("#### Cost Reduction Tips")
    st.warning(
        "- Reduce `DATA_RETENTION_TIME_IN_DAYS` on large tables/schemas\n"
        "- Drop unused tables, schemas, and databases\n"
        "- Use `TRANSIENT` tables where Failsafe is not needed\n"
        "- Purge expired stages and internal stages\n"
        "- Compress data with `ZSTD` or `SNAPPY` formats"
    )

st.markdown("---")

# ── Top tables by storage ─────────────────────────────────────────────────────
st.subheader("Top 100 Tables by Storage")

with st.spinner("Loading table storage…"):
    table_df = run_query(STORAGE_BY_TABLE_TOP)

if not table_df.empty:
    table_df.columns = [c.lower() for c in table_df.columns]
    table_df["monthly_cost_usd"] = (table_df["total_gb"] / 1024 * storage_rate).map("${:,.2f}".format)

    search = st.text_input("Filter by table/database name", placeholder="e.g. MY_DATABASE")
    if search:
        mask = (
            table_df["table_name"].str.contains(search, case=False, na=False) |
            table_df["database_name"].str.contains(search, case=False, na=False)
        )
        table_df = table_df[mask]

    st.dataframe(table_df, use_container_width=True, hide_index=True)

st.markdown("---")

# ── Stage storage ─────────────────────────────────────────────────────────────
st.subheader("Stage Storage")

with st.spinner("Loading stage data…"):
    stage_df = run_query(STORAGE_STAGE_USAGE)

if not stage_df.empty:
    stage_df.columns = [c.lower() for c in stage_df.columns]
    stage_df["monthly_cost_usd"] = (stage_df["stage_gb"] / 1024 * storage_rate).map("${:,.2f}".format)

    fig4 = px.bar(
        stage_df.head(20).sort_values("stage_gb"),
        x="stage_gb", y="stage_name", orientation="h",
        color="stage_type",
        title="Top Stages by Storage (GB)",
        labels={"stage_gb": "GB", "stage_name": "Stage"},
    )
    fig4.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(autorange="reversed"),
        height=max(300, min(len(stage_df), 20) * 40),
    )
    st.plotly_chart(fig4, use_container_width=True)
    st.dataframe(stage_df, use_container_width=True, hide_index=True)
