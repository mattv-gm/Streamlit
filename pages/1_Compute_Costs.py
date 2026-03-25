"""
Compute Costs Page
==================
Warehouse credit consumption: by warehouse, by day, cloud-services adjustments.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from utils.snowflake_connector import run_query
from utils.queries import (
    COMPUTE_BY_WAREHOUSE,
    COMPUTE_DAILY_BY_WAREHOUSE,
    COMPUTE_HOURLY_TREND,
    COMPUTE_CLOUD_SERVICES_ADJUSTMENT,
    WAREHOUSE_SETTINGS,
    date_filter,
)

st.set_page_config(page_title="Compute Costs | Snowflake Monitor", page_icon="💻", layout="wide")

# ── Sidebar controls ──────────────────────────────────────────────────────────
with st.sidebar:
    st.title("💻 Compute Costs")
    days = st.selectbox("Look-back period", [7, 14, 30, 60, 90], index=2,
                        format_func=lambda d: f"Last {d} days")
    credit_rate = st.number_input("Credit rate (USD)", 0.5, 50.0, 3.0, 0.25)
    st.markdown("---")
    st.caption("Source: WAREHOUSE_METERING_HISTORY")

DF = date_filter(days)

st.title("💻 Compute Costs")
st.caption(f"Last {days} days · ${credit_rate:.2f}/credit")
st.markdown("---")

# ── Per-warehouse summary ─────────────────────────────────────────────────────
st.subheader("Credits by Warehouse")

with st.spinner("Loading warehouse data…"):
    wh_df = run_query(COMPUTE_BY_WAREHOUSE.format(date_filter=DF))

if wh_df.empty:
    st.warning("No warehouse metering data found.")
    st.stop()

wh_df.columns = [c.lower() for c in wh_df.columns]
wh_df["est_cost_usd"] = wh_df["total_credits"] * credit_rate

col_bar, col_tbl = st.columns([3, 2])

with col_bar:
    fig = px.bar(
        wh_df.sort_values("total_credits"),
        x="total_credits",
        y="warehouse_name",
        orientation="h",
        color="compute_credits",
        color_continuous_scale="Blues",
        title="Total Credits per Warehouse",
        labels={"total_credits": "Credits", "warehouse_name": "Warehouse"},
        text="total_credits",
    )
    fig.update_traces(texttemplate="%{text:,.1f}", textposition="outside")
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(autorange="reversed"),
        coloraxis_showscale=False,
        height=max(300, len(wh_df) * 40),
    )
    st.plotly_chart(fig, use_container_width=True)

with col_tbl:
    display = wh_df[["warehouse_name", "compute_credits", "cloud_svc_credits",
                      "total_credits", "active_days", "est_cost_usd"]].copy()
    display["est_cost_usd"] = display["est_cost_usd"].map("${:,.0f}".format)
    display.columns = ["Warehouse", "Compute", "Cloud Svc", "Total", "Active Days", "Est. Cost"]
    st.dataframe(display, use_container_width=True, hide_index=True)

st.markdown("---")

# ── Daily trend by warehouse ──────────────────────────────────────────────────
st.subheader("Daily Credits by Warehouse")

with st.spinner("Loading daily trend…"):
    daily_df = run_query(COMPUTE_DAILY_BY_WAREHOUSE.format(date_filter=DF))

if not daily_df.empty:
    daily_df.columns = [c.lower() for c in daily_df.columns]
    daily_df["usage_date"] = pd.to_datetime(daily_df["usage_date"])

    # Warehouse filter
    all_wh = sorted(daily_df["warehouse_name"].unique())
    selected_wh = st.multiselect("Filter warehouses", all_wh, default=all_wh[:10])
    filtered = daily_df[daily_df["warehouse_name"].isin(selected_wh)] if selected_wh else daily_df

    fig2 = px.area(
        filtered,
        x="usage_date",
        y="total_credits",
        color="warehouse_name",
        title="Credit Usage Over Time",
        labels={"usage_date": "Date", "total_credits": "Credits", "warehouse_name": "Warehouse"},
    )
    fig2.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
    )
    st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# ── Hourly heatmap ────────────────────────────────────────────────────────────
st.subheader("Hourly Credit Consumption (All Warehouses)")

with st.spinner("Loading hourly data…"):
    hourly_df = run_query(COMPUTE_HOURLY_TREND.format(date_filter=DF))

if not hourly_df.empty:
    hourly_df.columns = [c.lower() for c in hourly_df.columns]
    hourly_df["usage_hour"] = pd.to_datetime(hourly_df["usage_hour"])
    hourly_df["day"] = hourly_df["usage_hour"].dt.date.astype(str)
    hourly_df["hour"] = hourly_df["usage_hour"].dt.hour

    pivot = hourly_df.pivot_table(index="day", columns="hour", values="total_credits", aggfunc="sum").fillna(0)

    fig3 = px.imshow(
        pivot,
        aspect="auto",
        color_continuous_scale="Blues",
        title="Credit Usage Heatmap (Day × Hour)",
        labels=dict(x="Hour of Day", y="Date", color="Credits"),
    )
    fig3.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig3, use_container_width=True)

st.markdown("---")

# ── Cloud services adjustment ─────────────────────────────────────────────────
st.subheader("Cloud Services Adjustment (10% Rule)")
st.caption(
    "Snowflake provides a daily credit adjustment: if cloud-services credits "
    "are ≤ 10% of total compute credits, they are free. This section shows net billed cloud-services credits."
)

with st.spinner("Loading cloud services data…"):
    adj_df = run_query(COMPUTE_CLOUD_SERVICES_ADJUSTMENT.format(date_filter=DF))

if not adj_df.empty:
    adj_df.columns = [c.lower() for c in adj_df.columns]
    adj_df["usage_date"] = pd.to_datetime(adj_df["usage_date"])

    fig4 = go.Figure()
    fig4.add_trace(go.Bar(x=adj_df["usage_date"], y=adj_df["cloud_svc_credits"],
                          name="Gross Cloud Svc Credits", marker_color="#29B5E8"))
    fig4.add_trace(go.Scatter(x=adj_df["usage_date"], y=adj_df["net_cloud_svc_credits"],
                              name="Net Cloud Svc Credits (after adj.)",
                              line=dict(color="#FF6B6B", width=2), mode="lines+markers"))
    fig4.update_layout(
        title="Cloud Services Credits — Gross vs. Net",
        xaxis_title="Date", yaxis_title="Credits",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        barmode="overlay",
    )
    st.plotly_chart(fig4, use_container_width=True)

st.markdown("---")

# ── Warehouse configuration ───────────────────────────────────────────────────
st.subheader("Warehouse Configuration")

with st.spinner("Loading warehouse settings…"):
    settings_df = run_query(WAREHOUSE_SETTINGS)

if not settings_df.empty:
    settings_df.columns = [c.lower() for c in settings_df.columns]
    keep = ["warehouse_name", "type", "size", "min_cluster_count", "max_cluster_count",
            "scaling_policy", "auto_suspend", "auto_resume", "resource_monitor", "owner"]
    avail = [c for c in keep if c in settings_df.columns]

    def highlight_no_autosuspend(row):
        styles = [""] * len(row)
        if "auto_suspend" in row.index:
            val = row["auto_suspend"]
            if val is None or str(val) in ("0", "None", ""):
                idx = list(row.index).index("auto_suspend")
                styles[idx] = "background-color: #8B0000; color: white"
        return styles

    styled = settings_df[avail].style.apply(highlight_no_autosuspend, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)
    st.caption("Red cells = Auto-suspend disabled (potential cost risk).")
