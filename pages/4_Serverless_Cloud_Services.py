"""
Serverless & Cloud Services Page
=================================
Credits consumed by: Snowpipe, Tasks, Materialized Views, Auto-Clustering,
Search Optimization, Replication, and overall Cloud Services.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from utils.snowflake_connector import run_query
from utils.queries import (
    SERVERLESS_CREDITS,
    SNOWPIPE_COSTS,
    TASK_COSTS,
    REPLICATION_COSTS,
    SEARCH_OPTIMIZATION_COSTS,
    MATERIALIZED_VIEW_COSTS,
    CLUSTERING_COSTS,
    date_filter,
)

st.set_page_config(
    page_title="Serverless & Cloud Services | Snowflake Monitor",
    page_icon="⚙️", layout="wide",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Serverless & Cloud Services")
    days = st.selectbox("Look-back period", [7, 14, 30, 60, 90], index=2,
                        format_func=lambda d: f"Last {d} days")
    credit_rate = st.number_input("Credit rate (USD)", 0.5, 50.0, 3.0, 0.25)
    st.markdown("---")
    st.caption("Source: METERING_HISTORY, PIPE_USAGE_HISTORY, TASK_HISTORY, etc.")

DF = date_filter(days)

st.title("⚙️ Serverless & Cloud Services")
st.caption(f"Last {days} days · ${credit_rate:.2f}/credit")
st.markdown("---")

# ── Serverless credit overview ────────────────────────────────────────────────
st.subheader("Serverless Credit Consumption by Service")

with st.spinner("Loading serverless credits…"):
    svc_df = run_query(SERVERLESS_CREDITS.format(date_filter=DF))

if not svc_df.empty:
    svc_df.columns = [c.lower() for c in svc_df.columns]
    svc_df["est_cost_usd"] = svc_df["total_credits"] * credit_rate

    c_pie, c_tbl = st.columns(2)
    with c_pie:
        fig = px.pie(
            svc_df, names="service_type", values="total_credits", hole=0.4,
            title="Serverless Credits by Service Type",
            color_discrete_sequence=px.colors.qualitative.Set3,
        )
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    with c_tbl:
        display = svc_df.copy()
        display["est_cost_usd"] = display["est_cost_usd"].map("${:,.2f}".format)
        display.columns = ["Service Type", "Total Credits", "Est. Cost (USD)"]
        st.dataframe(display, use_container_width=True, hide_index=True)

        total_svc_credits = svc_df["total_credits"].sum()
        st.metric("Total Serverless Credits", f"{total_svc_credits:,.2f}",
                  help="Excludes VIRTUAL_WAREHOUSE and CLOUD_SERVICES")
        st.caption(f"≈ ${total_svc_credits * credit_rate:,.0f}")
else:
    st.info("No serverless service data found for this period.")

st.markdown("---")

# ── Tabs for each service ─────────────────────────────────────────────────────
tab_pipe, tab_task, tab_mv, tab_cluster, tab_search, tab_rep = st.tabs([
    "🚿 Snowpipe", "⏰ Tasks", "🪞 Materialized Views",
    "🔀 Auto-Clustering", "🔎 Search Optimization", "🔁 Replication",
])

# ── Snowpipe ──────────────────────────────────────────────────────────────────
with tab_pipe:
    st.subheader("Snowpipe Credit Usage")
    st.caption("Snowpipe is a serverless continuous-ingestion service billed per credit.")

    with st.spinner("Loading Snowpipe data…"):
        pipe_df = run_query(SNOWPIPE_COSTS.format(date_filter=DF))

    if pipe_df.empty:
        st.info("No Snowpipe usage found.")
    else:
        pipe_df.columns = [c.lower() for c in pipe_df.columns]
        pipe_df["usage_date"] = pd.to_datetime(pipe_df["usage_date"])

        # Summary
        total_pipe = pipe_df["credits_used"].sum()
        total_gb   = pipe_df["gb_inserted"].sum()
        total_files = pipe_df["files_inserted"].sum()

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Credits", f"{total_pipe:,.4f}")
        m1.caption(f"≈ ${total_pipe * credit_rate:,.2f}")
        m2.metric("Total GB Inserted", f"{total_gb:,.2f}")
        m3.metric("Total Files Inserted", f"{total_files:,}")

        # Per-pipe breakdown
        pipe_summary = pipe_df.groupby("pipe_name")[["credits_used", "gb_inserted", "files_inserted"]].sum().reset_index()
        fig = px.bar(
            pipe_summary.sort_values("credits_used", ascending=False).head(20),
            x="pipe_name", y="credits_used",
            title="Credits by Pipe",
            color="credits_used", color_continuous_scale="Blues",
        )
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                          coloraxis_showscale=False, xaxis_tickangle=-30)
        st.plotly_chart(fig, use_container_width=True)

        # Daily trend
        daily_pipe = pipe_df.groupby("usage_date")[["credits_used", "gb_inserted"]].sum().reset_index()
        fig2 = px.line(daily_pipe, x="usage_date", y="credits_used",
                       title="Daily Snowpipe Credit Trend", markers=True,
                       color_discrete_sequence=["#29B5E8"])
        fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)

        st.dataframe(pipe_df, use_container_width=True, hide_index=True)

# ── Tasks ─────────────────────────────────────────────────────────────────────
with tab_task:
    st.subheader("Snowflake Task Credit Usage")
    st.caption("Serverless tasks are billed by compute time; user-managed tasks use warehouse credits.")

    with st.spinner("Loading task data…"):
        task_df = run_query(TASK_COSTS.format(date_filter=DF))

    if task_df.empty:
        st.info("No task usage found.")
    else:
        task_df.columns = [c.lower() for c in task_df.columns]

        total_task_credits = task_df["cloud_svc_credits"].sum()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Tasks", f"{len(task_df):,}")
        m2.metric("Cloud Svc Credits", f"{total_task_credits:,.4f}")
        m2.caption(f"≈ ${total_task_credits * credit_rate:,.2f}")
        total_runs = task_df["run_count"].sum()
        m3.metric("Total Runs", f"{total_runs:,}")
        if total_runs > 0:
            success_rate = task_df["success_count"].sum() / total_runs * 100
            m4.metric("Success Rate", f"{success_rate:.1f}%")

        # Top tasks by credit
        fig = px.bar(
            task_df.sort_values("cloud_svc_credits", ascending=False).head(20),
            x="task_name", y="cloud_svc_credits",
            color="failure_count",
            title="Top Tasks by Cloud Services Credits",
            color_continuous_scale="Reds",
        )
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                          xaxis_tickangle=-30)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(task_df, use_container_width=True, hide_index=True)

# ── Materialized Views ────────────────────────────────────────────────────────
with tab_mv:
    st.subheader("Materialized View Refresh Costs")
    st.caption("Snowflake automatically refreshes MVs in the background, consuming credits.")

    with st.spinner("Loading MV data…"):
        mv_df = run_query(MATERIALIZED_VIEW_COSTS.format(date_filter=DF))

    if mv_df.empty:
        st.info("No materialized view refresh data found.")
    else:
        mv_df.columns = [c.lower() for c in mv_df.columns]
        mv_df["usage_date"] = pd.to_datetime(mv_df["usage_date"])

        total_mv = mv_df["credits_used"].sum()
        st.metric("Total MV Credits", f"{total_mv:,.4f}")
        st.caption(f"≈ ${total_mv * credit_rate:,.2f}")

        # Per-MV summary
        mv_summary = mv_df.groupby(["database_name", "schema_name", "table_name"])[
            ["credits_used", "gb_refreshed"]].sum().reset_index()

        fig = px.treemap(
            mv_summary, path=["database_name", "schema_name", "table_name"],
            values="credits_used", color="credits_used",
            color_continuous_scale="Blues",
            title="MV Credits Treemap",
        )
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(mv_df, use_container_width=True, hide_index=True)

# ── Auto-Clustering ───────────────────────────────────────────────────────────
with tab_cluster:
    st.subheader("Automatic Clustering Costs")
    st.caption("Auto-clustering reorganizes data in clustered tables, consuming serverless credits.")

    with st.spinner("Loading clustering data…"):
        cl_df = run_query(CLUSTERING_COSTS.format(date_filter=DF))

    if cl_df.empty:
        st.info("No automatic clustering data found.")
    else:
        cl_df.columns = [c.lower() for c in cl_df.columns]
        cl_df["usage_date"] = pd.to_datetime(cl_df["usage_date"])

        total_cl = cl_df["credits_used"].sum()
        m1, m2 = st.columns(2)
        m1.metric("Total Clustering Credits", f"{total_cl:,.4f}")
        m1.caption(f"≈ ${total_cl * credit_rate:,.2f}")
        m2.metric("Tables Clustered", f"{cl_df['table_name'].nunique():,}")

        # Daily trend
        daily_cl = cl_df.groupby("usage_date")["credits_used"].sum().reset_index()
        fig = px.bar(daily_cl, x="usage_date", y="credits_used",
                     title="Daily Clustering Credits",
                     color_discrete_sequence=["#44D7B6"])
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

        # By table
        cl_summary = cl_df.groupby(["database_name", "schema_name", "table_name"])[
            ["credits_used", "gb_reclustered"]].sum().reset_index()
        fig2 = px.bar(
            cl_summary.sort_values("credits_used", ascending=False).head(20),
            x="credits_used", y="table_name", orientation="h",
            title="Top Clustered Tables by Credits",
        )
        fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                           yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig2, use_container_width=True)
        st.dataframe(cl_df, use_container_width=True, hide_index=True)

# ── Search Optimization ───────────────────────────────────────────────────────
with tab_search:
    st.subheader("Search Optimization Service Costs")
    st.caption("Search Optimization Service (SOS) improves point-lookup query performance.")

    with st.spinner("Loading search optimization data…"):
        so_df = run_query(SEARCH_OPTIMIZATION_COSTS.format(date_filter=DF))

    if so_df.empty:
        st.info("No search optimization data found.")
    else:
        so_df.columns = [c.lower() for c in so_df.columns]
        so_df["usage_date"] = pd.to_datetime(so_df["usage_date"])

        total_so = so_df["credits_used"].sum()
        st.metric("Total SOS Credits", f"{total_so:,.4f}")
        st.caption(f"≈ ${total_so * credit_rate:,.2f}")

        # Daily
        daily_so = so_df.groupby("usage_date")["credits_used"].sum().reset_index()
        fig = px.line(daily_so, x="usage_date", y="credits_used",
                      title="Daily Search Optimization Credits", markers=True,
                      color_discrete_sequence=["#FF6B6B"])
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(so_df, use_container_width=True, hide_index=True)

# ── Replication ───────────────────────────────────────────────────────────────
with tab_rep:
    st.subheader("Database Replication Costs")
    st.caption("Cross-region/cross-cloud replication incurs compute credits and data-transfer fees.")

    with st.spinner("Loading replication data…"):
        rep_df = run_query(REPLICATION_COSTS.format(date_filter=DF))

    if rep_df.empty:
        st.info("No replication data found.")
    else:
        rep_df.columns = [c.lower() for c in rep_df.columns]
        rep_df["replication_date"] = pd.to_datetime(rep_df["replication_date"])

        total_rep = rep_df["credits_used"].sum()
        total_gb_rep = rep_df["gb_transferred"].sum()
        m1, m2 = st.columns(2)
        m1.metric("Total Replication Credits", f"{total_rep:,.4f}")
        m1.caption(f"≈ ${total_rep * credit_rate:,.2f}")
        m2.metric("Total GB Transferred", f"{total_gb_rep:,.2f}")

        rep_summary = rep_df.groupby("database_name")[["credits_used", "gb_transferred"]].sum().reset_index()
        fig = px.bar(
            rep_summary, x="database_name", y="credits_used",
            color="gb_transferred", color_continuous_scale="Purples",
            title="Replication Credits by Database",
        )
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(rep_df, use_container_width=True, hide_index=True)
