"""
Warehouse Efficiency Page
==========================
Idle time, queuing, query duration distributions, sizing recommendations,
and data-transfer costs.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from utils.snowflake_connector import run_query
from utils.queries import (
    WAREHOUSE_EFFICIENCY,
    WAREHOUSE_IDLE_ANALYSIS,
    WAREHOUSE_QUERY_DISTRIBUTION,
    DATA_TRANSFER_DAILY,
    DATA_TRANSFER_BY_DIRECTION,
    LOGIN_ACTIVITY,
    date_filter,
)

st.set_page_config(
    page_title="Warehouse Efficiency | Snowflake Monitor",
    page_icon="🏭", layout="wide",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🏭 Warehouse Efficiency")
    days = st.selectbox("Look-back period", [7, 14, 30, 60, 90], index=2,
                        format_func=lambda d: f"Last {d} days")
    credit_rate = st.number_input("Credit rate (USD)", 0.5, 50.0, 3.0, 0.25)
    st.markdown("---")
    st.caption("Source: QUERY_HISTORY, WAREHOUSE_METERING_HISTORY, DATA_TRANSFER_HISTORY")

DF = date_filter(days)

st.title("🏭 Warehouse Efficiency & Data Transfer")
st.caption(f"Last {days} days · ${credit_rate:.2f}/credit")
st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_idle, tab_queue, tab_dist, tab_transfer, tab_login = st.tabs([
    "⏸️ Idle Analysis",
    "⏳ Queuing & Efficiency",
    "📊 Query Distribution",
    "🌐 Data Transfer",
    "🔐 Login Activity",
])

# ── Idle Analysis ─────────────────────────────────────────────────────────────
with tab_idle:
    st.subheader("Warehouse Idle-Time Analysis")
    st.caption(
        "Warehouses consume credits when running even with no queries. "
        "Low utilization % indicates wasted spend."
    )

    with st.spinner("Loading idle analysis…"):
        idle_df = run_query(WAREHOUSE_IDLE_ANALYSIS.format(date_filter=DF))

    if idle_df.empty:
        st.info("No idle data found.")
    else:
        idle_df.columns = [c.lower() for c in idle_df.columns]
        idle_df["wasted_credits_est"] = (
            idle_df["idle_hours"] / idle_df["total_hours"].replace(0, 1) * idle_df["total_credits"]
        ).round(2)

        # Color code utilization
        def util_color(val):
            if val is None:
                return ""
            val = float(val)
            if val < 20:
                return "background-color: #8B0000; color: white"
            elif val < 50:
                return "background-color: #FF8C00; color: black"
            return ""

        c_chart, c_tbl = st.columns([3, 2])

        with c_chart:
            fig = px.bar(
                idle_df.sort_values("utilization_pct"),
                x="utilization_pct", y="warehouse_name",
                orientation="h",
                color="utilization_pct",
                color_continuous_scale=["#8B0000", "#FF8C00", "#44D7B6"],
                range_color=[0, 100],
                title="Warehouse Utilization % (Active Hours / Total Hours)",
                labels={"utilization_pct": "Utilization %", "warehouse_name": "Warehouse"},
                text="utilization_pct",
            )
            fig.add_vline(x=50, line_dash="dash", line_color="yellow",
                          annotation_text="50% threshold", annotation_position="top right")
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                coloraxis_showscale=False,
                height=max(300, len(idle_df) * 45),
            )
            st.plotly_chart(fig, use_container_width=True)

        with c_tbl:
            display = idle_df[["warehouse_name", "total_hours", "active_hours",
                               "idle_hours", "utilization_pct", "total_credits",
                               "wasted_credits_est"]].copy()
            display["wasted_cost"] = (display["wasted_credits_est"] * credit_rate).map("${:,.0f}".format)
            display.columns = ["Warehouse", "Total Hrs", "Active Hrs", "Idle Hrs",
                               "Util %", "Total Credits", "Est. Wasted Credits", "Est. Wasted $"]
            styled = display.style.applymap(util_color, subset=["Util %"])
            st.dataframe(styled, use_container_width=True, hide_index=True)

        total_wasted = idle_df["wasted_credits_est"].sum()
        st.warning(
            f"Estimated **{total_wasted:,.1f} credits** (≈ **${total_wasted * credit_rate:,.0f}**) "
            f"potentially wasted on idle warehouses. "
            "Consider reducing `AUTO_SUSPEND` settings."
        )

# ── Queuing & Efficiency ──────────────────────────────────────────────────────
with tab_queue:
    st.subheader("Warehouse Queuing & Query Efficiency")
    st.caption(
        "High `queued_overload_time` suggests the warehouse is undersized. "
        "High `queued_provisioning_time` means the warehouse starts cold frequently."
    )

    with st.spinner("Loading efficiency data…"):
        eff_df = run_query(WAREHOUSE_EFFICIENCY.format(date_filter=DF))

    if eff_df.empty:
        st.info("No efficiency data found.")
    else:
        eff_df.columns = [c.lower() for c in eff_df.columns]

        col1, col2 = st.columns(2)

        with col1:
            fig = px.bar(
                eff_df.sort_values("avg_overload_queue_sec", ascending=False).head(15),
                x="warehouse_name", y=["avg_overload_queue_sec", "avg_provision_queue_sec"],
                title="Avg Queue Time (sec) by Warehouse",
                barmode="stack",
                color_discrete_map={
                    "avg_overload_queue_sec": "#FF6B6B",
                    "avg_provision_queue_sec": "#FFD700",
                },
                labels={"value": "Seconds", "variable": "Queue Type"},
            )
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                xaxis_tickangle=-30,
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig2 = px.scatter(
                eff_df,
                x="avg_elapsed_sec", y="success_pct",
                size="session_count",
                color="avg_overload_queue_sec",
                hover_name="warehouse_name",
                color_continuous_scale="Reds",
                title="Avg Duration vs. Success Rate (bubble = query count)",
                labels={
                    "avg_elapsed_sec": "Avg Elapsed (sec)",
                    "success_pct": "Success %",
                    "avg_overload_queue_sec": "Avg Overload Queue (sec)",
                },
            )
            fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2, use_container_width=True)

        st.dataframe(eff_df, use_container_width=True, hide_index=True)

# ── Query Duration Distribution ───────────────────────────────────────────────
with tab_dist:
    st.subheader("Query Duration Distribution by Warehouse")
    st.caption(
        "A large % of sub-1s queries on a large warehouse = potential over-sizing. "
        "A large % of 60s+ queries = potential under-sizing."
    )

    with st.spinner("Loading query distribution…"):
        dist_df = run_query(WAREHOUSE_QUERY_DISTRIBUTION.format(date_filter=DF))

    if dist_df.empty:
        st.info("No distribution data found.")
    else:
        dist_df.columns = [c.lower() for c in dist_df.columns]

        # Stacked bar: duration buckets
        melt_df = dist_df.melt(
            id_vars=["warehouse_name", "warehouse_size", "total_queries"],
            value_vars=["pct_under_1s", "pct_1_10s", "pct_10_60s", "pct_over_60s"],
            var_name="duration_bucket", value_name="percentage",
        )
        bucket_labels = {
            "pct_under_1s": "< 1s",
            "pct_1_10s": "1–10s",
            "pct_10_60s": "10–60s",
            "pct_over_60s": "> 60s",
        }
        melt_df["duration_bucket"] = melt_df["duration_bucket"].map(bucket_labels)

        top_wh = dist_df.nlargest(20, "total_queries")["warehouse_name"].tolist()
        melt_filtered = melt_df[melt_df["warehouse_name"].isin(top_wh)]

        fig = px.bar(
            melt_filtered,
            x="warehouse_name", y="percentage",
            color="duration_bucket",
            title="Query Duration Buckets by Warehouse (Top 20 by Volume)",
            barmode="stack",
            color_discrete_map={
                "< 1s": "#44D7B6",
                "1–10s": "#29B5E8",
                "10–60s": "#FFD700",
                "> 60s": "#FF6B6B",
            },
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            xaxis_tickangle=-30,
            yaxis_title="% of Queries",
            legend_title="Duration",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Sizing recommendations
        st.subheader("Sizing Insights")
        for _, row in dist_df.iterrows():
            wh = row.get("warehouse_name", "?")
            size = row.get("warehouse_size", "?")
            under_1s = float(row.get("pct_under_1s", 0) or 0)
            over_60s  = float(row.get("pct_over_60s", 0) or 0)

            if under_1s > 70:
                st.warning(f"**{wh}** ({size}): {under_1s:.0f}% of queries < 1s — consider downsizing.")
            elif over_60s > 30:
                st.error(f"**{wh}** ({size}): {over_60s:.0f}% of queries > 60s — consider upsizing.")

# ── Data Transfer ─────────────────────────────────────────────────────────────
with tab_transfer:
    st.subheader("Data Transfer Costs")
    st.caption(
        "Data transfers within the same cloud/region are free. "
        "Cross-region and cross-cloud transfers incur charges (~$0.08–$0.18/GB)."
    )

    with st.spinner("Loading data transfer…"):
        xfer_df = run_query(DATA_TRANSFER_DAILY.format(date_filter=DF))
        dir_df  = run_query(DATA_TRANSFER_BY_DIRECTION.format(date_filter=DF))

    if xfer_df.empty:
        st.info("No data transfer events found.")
    else:
        xfer_df.columns = [c.lower() for c in xfer_df.columns]
        xfer_df["transfer_date"] = pd.to_datetime(xfer_df["transfer_date"])

        total_gb = xfer_df["gb_transferred"].sum()
        # Rough cost estimate: $0.08–0.18/GB for cross-region
        est_transfer_cost = total_gb * 0.12
        m1, m2 = st.columns(2)
        m1.metric("Total GB Transferred", f"{total_gb:,.2f}")
        m2.metric("Est. Transfer Cost", f"${est_transfer_cost:,.2f}",
                  help="Rough estimate at $0.12/GB (varies by cloud/region pair)")

        # Daily trend
        daily_xfer = xfer_df.groupby(["transfer_date", "transfer_type"])["gb_transferred"].sum().reset_index()
        fig = px.bar(daily_xfer, x="transfer_date", y="gb_transferred",
                     color="transfer_type",
                     title="Daily Data Transfer by Type (GB)",
                     labels={"gb_transferred": "GB", "transfer_date": "Date"})
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

        # By source/target
        if not dir_df.empty:
            dir_df.columns = [c.lower() for c in dir_df.columns]
            fig2 = px.sunburst(
                dir_df, path=["source", "target", "transfer_type"],
                values="gb_transferred",
                title="Transfer Volume: Source → Target (GB)",
                color="gb_transferred", color_continuous_scale="Blues",
            )
            fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2, use_container_width=True)

        st.dataframe(xfer_df, use_container_width=True, hide_index=True)

# ── Login Activity ────────────────────────────────────────────────────────────
with tab_login:
    st.subheader("User Login Activity")
    st.caption("Orphaned/stale accounts with active sessions may be running unneeded warehouses.")

    with st.spinner("Loading login activity…"):
        login_df = run_query(LOGIN_ACTIVITY.format(date_filter=DF))

    if login_df.empty:
        st.info("No login data found.")
    else:
        login_df.columns = [c.lower() for c in login_df.columns]

        c1, c2 = st.columns(2)

        with c1:
            fig = px.bar(
                login_df.head(20).sort_values("total_logins", ascending=False),
                x="user_name", y=["successful_logins", "failed_logins"],
                title="Top 20 Users by Login Activity",
                barmode="stack",
                color_discrete_map={"successful_logins": "#44D7B6", "failed_logins": "#FF6B6B"},
            )
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                xaxis_tickangle=-30,
            )
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            # Users with high failure rates
            login_df["failure_rate_pct"] = (
                login_df["failed_logins"] / login_df["total_logins"].replace(0, 1) * 100
            ).round(1)
            high_fail = login_df[login_df["failure_rate_pct"] > 20].head(15)
            if not high_fail.empty:
                fig2 = px.bar(
                    high_fail.sort_values("failure_rate_pct", ascending=False),
                    x="user_name", y="failure_rate_pct",
                    title="Users with >20% Login Failure Rate",
                    color="failure_rate_pct", color_continuous_scale="Reds",
                )
                fig2.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    xaxis_tickangle=-30, coloraxis_showscale=False,
                )
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.success("No users with high login failure rates found.")

        st.dataframe(login_df, use_container_width=True, hide_index=True)
