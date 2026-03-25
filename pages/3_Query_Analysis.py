"""
Query Analysis Page
===================
Identifies expensive queries, top consumers by user/warehouse, failures,
data-spill, and query volume trends.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from utils.snowflake_connector import run_query
from utils.queries import (
    QUERY_TOP_EXPENSIVE,
    QUERY_CREDITS_BY_USER,
    QUERY_CREDITS_BY_WAREHOUSE,
    QUERY_FAILED_COSTLY,
    QUERY_VOLUME_TREND,
    QUERY_BYTES_SPILLED,
    date_filter,
)

st.set_page_config(page_title="Query Analysis | Snowflake Monitor", page_icon="🔍", layout="wide")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🔍 Query Analysis")
    days = st.selectbox("Look-back period", [1, 3, 7, 14, 30], index=2,
                        format_func=lambda d: f"Last {d} days")
    st.markdown("---")
    st.caption("Source: QUERY_HISTORY")
    st.caption("Note: QUERY_HISTORY has a 3h latency and retains 365 days.")

DF = date_filter(days)

st.title("🔍 Query Analysis")
st.caption(f"Last {days} days")
st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_top, tab_user, tab_wh, tab_fail, tab_trend, tab_spill = st.tabs([
    "🏆 Top Expensive Queries",
    "👤 By User",
    "🏭 By Warehouse",
    "❌ Failed Queries",
    "📈 Volume Trend",
    "💧 Data Spill",
])

# ── Top Expensive Queries ─────────────────────────────────────────────────────
with tab_top:
    st.subheader("Top 100 Most Expensive Queries (by Elapsed Time)")

    with st.spinner("Loading query history…"):
        q_df = run_query(QUERY_TOP_EXPENSIVE.format(date_filter=DF))

    if q_df.empty:
        st.info("No query data found.")
    else:
        q_df.columns = [c.lower() for c in q_df.columns]

        # Filters
        fc1, fc2, fc3 = st.columns(3)
        users = ["All"] + sorted(q_df["user_name"].dropna().unique().tolist())
        warehouses = ["All"] + sorted(q_df["warehouse_name"].dropna().unique().tolist())
        min_sec = fc3.number_input("Min elapsed (sec)", min_value=0, value=0, step=1)
        sel_user = fc1.selectbox("Filter by user", users)
        sel_wh   = fc2.selectbox("Filter by warehouse", warehouses)

        mask = q_df["elapsed_sec"].fillna(0) >= min_sec
        if sel_user != "All":
            mask &= q_df["user_name"] == sel_user
        if sel_wh != "All":
            mask &= q_df["warehouse_name"] == sel_wh
        filtered = q_df[mask].copy()

        # Summary KPIs
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Queries shown", f"{len(filtered):,}")
        k2.metric("Total elapsed (hours)", f"{filtered['elapsed_sec'].sum()/3600:,.1f}")
        k3.metric("Avg elapsed (sec)", f"{filtered['elapsed_sec'].mean():,.1f}" if len(filtered) else "—")
        k4.metric("Total TB scanned", f"{filtered['gb_scanned'].sum()/1024:,.3f}" if "gb_scanned" in filtered else "—")

        # Distribution chart
        fig = px.histogram(
            filtered, x="elapsed_sec", nbins=40,
            title="Query Duration Distribution",
            labels={"elapsed_sec": "Elapsed (sec)"},
            color_discrete_sequence=["#29B5E8"],
        )
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

        # Table
        show_cols = ["query_id", "user_name", "warehouse_name", "warehouse_size",
                     "elapsed_sec", "execution_sec", "queued_overload_sec",
                     "gb_scanned", "rows_produced", "start_time"]
        avail_cols = [c for c in show_cols if c in filtered.columns]
        st.dataframe(filtered[avail_cols], use_container_width=True, hide_index=True)

        # Expandable query text viewer
        st.subheader("Query Text Viewer")
        if "query_id" in filtered.columns and "query_text" in filtered.columns:
            qids = filtered["query_id"].tolist()
            sel_qid = st.selectbox("Select Query ID", qids[:20])
            if sel_qid:
                row = filtered[filtered["query_id"] == sel_qid].iloc[0]
                st.code(row.get("query_text", "N/A"), language="sql")
                info_cols = ["user_name", "warehouse_name", "elapsed_sec",
                             "execution_sec", "gb_scanned", "rows_produced"]
                avail_info = {c: row[c] for c in info_cols if c in row.index}
                st.json(avail_info)

# ── By User ───────────────────────────────────────────────────────────────────
with tab_user:
    st.subheader("Credit & Query Activity by User")

    with st.spinner("Loading user data…"):
        user_df = run_query(QUERY_CREDITS_BY_USER.format(date_filter=DF))

    if user_df.empty:
        st.info("No user data found.")
    else:
        user_df.columns = [c.lower() for c in user_df.columns]

        col1, col2 = st.columns(2)

        with col1:
            fig = px.bar(
                user_df.head(20).sort_values("cloud_svc_credits"),
                x="cloud_svc_credits", y="user_name", orientation="h",
                title="Top 20 Users by Cloud Services Credits",
                color="cloud_svc_credits", color_continuous_scale="Blues",
                labels={"cloud_svc_credits": "Credits", "user_name": "User"},
            )
            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                              coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig2 = px.scatter(
                user_df,
                x="query_count", y="avg_elapsed_sec",
                size="total_tb_scanned",
                color="cloud_svc_credits",
                hover_name="user_name",
                title="Query Count vs. Avg Duration (bubble = TB scanned)",
                labels={
                    "query_count": "Query Count",
                    "avg_elapsed_sec": "Avg Elapsed (sec)",
                    "cloud_svc_credits": "Cloud Svc Credits",
                },
                color_continuous_scale="Reds",
            )
            fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2, use_container_width=True)

        st.dataframe(user_df, use_container_width=True, hide_index=True)

# ── By Warehouse ──────────────────────────────────────────────────────────────
with tab_wh:
    st.subheader("Credit & Query Activity by Warehouse")

    with st.spinner("Loading warehouse query data…"):
        wh_q_df = run_query(QUERY_CREDITS_BY_WAREHOUSE.format(date_filter=DF))

    if wh_q_df.empty:
        st.info("No warehouse query data found.")
    else:
        wh_q_df.columns = [c.lower() for c in wh_q_df.columns]

        fig = px.bar(
            wh_q_df.sort_values("cloud_svc_credits", ascending=False),
            x="warehouse_name", y=["cloud_svc_credits", "query_count"],
            barmode="group",
            title="Cloud Services Credits and Query Count by Warehouse",
        )
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(wh_q_df, use_container_width=True, hide_index=True)

# ── Failed Queries ────────────────────────────────────────────────────────────
with tab_fail:
    st.subheader("Failed / Errored Queries")
    st.caption("Failed queries may still consume cloud services credits.")

    with st.spinner("Loading failed queries…"):
        fail_df = run_query(QUERY_FAILED_COSTLY.format(date_filter=DF))

    if fail_df.empty:
        st.success("No failed queries found.")
    else:
        fail_df.columns = [c.lower() for c in fail_df.columns]

        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(
                fail_df.head(15),
                x="failure_count", y="user_name",
                orientation="h", color="total_cloud_svc_credits",
                title="Failures by User (colored by credits consumed)",
                color_continuous_scale="Oranges",
            )
            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                              yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            if "error_code" in fail_df.columns:
                err_counts = fail_df.groupby("error_code")["failure_count"].sum().reset_index()
                fig2 = px.pie(err_counts, names="error_code", values="failure_count",
                              title="Failure Distribution by Error Code")
                fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig2, use_container_width=True)

        st.dataframe(fail_df, use_container_width=True, hide_index=True)

# ── Volume Trend ──────────────────────────────────────────────────────────────
with tab_trend:
    st.subheader("Daily Query Volume Trend")

    with st.spinner("Loading volume trend…"):
        vol_df = run_query(QUERY_VOLUME_TREND.format(date_filter=DF))

    if vol_df.empty:
        st.info("No trend data found.")
    else:
        vol_df.columns = [c.lower() for c in vol_df.columns]
        vol_df["query_date"] = pd.to_datetime(vol_df["query_date"])

        fig = px.bar(
            vol_df, x="query_date", y="query_count",
            color="execution_status",
            title="Daily Query Count by Status",
            color_discrete_map={"SUCCESS": "#44D7B6", "FAILED": "#FF6B6B", "INCIDENT": "#FFD700"},
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
        )
        st.plotly_chart(fig, use_container_width=True)

        fig2 = px.line(
            vol_df[vol_df["execution_status"] == "SUCCESS"],
            x="query_date", y=["avg_elapsed_sec", "total_tb_scanned"],
            title="Avg Query Duration & TB Scanned (Successful Queries)",
        )
        fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)

# ── Data Spill ────────────────────────────────────────────────────────────────
with tab_spill:
    st.subheader("Data Spill to Disk")
    st.caption(
        "Spilling to local storage is cheap; spilling to remote storage incurs significant I/O cost. "
        "Reduce spill by increasing warehouse size, optimizing queries, or using result caching."
    )

    with st.spinner("Loading spill data…"):
        spill_df = run_query(QUERY_BYTES_SPILLED.format(date_filter=DF))

    if spill_df.empty:
        st.success("No spill data found — great!")
    else:
        spill_df.columns = [c.lower() for c in spill_df.columns]
        spill_df["query_date"] = pd.to_datetime(spill_df["query_date"])

        total_local  = spill_df["local_spill_gb"].sum()
        total_remote = spill_df["remote_spill_gb"].sum()

        m1, m2 = st.columns(2)
        m1.metric("Total Local Spill", f"{total_local:,.2f} GB",
                  help="Spill to local SSD — performance impact only")
        m2.metric("Total Remote Spill", f"{total_remote:,.2f} GB",
                  help="Spill to remote storage — expensive and slow",
                  delta=f"{total_remote:+,.2f} GB", delta_color="inverse")

        fig = go.Figure()
        fig.add_trace(go.Bar(x=spill_df["query_date"], y=spill_df["local_spill_gb"],
                             name="Local Spill (GB)", marker_color="#FFD700"))
        fig.add_trace(go.Bar(x=spill_df["query_date"], y=spill_df["remote_spill_gb"],
                             name="Remote Spill (GB)", marker_color="#FF6B6B"))
        fig.update_layout(
            barmode="stack",
            title="Daily Data Spill (GB)",
            xaxis_title="Date", yaxis_title="GB",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)
