"""
AI & Cortex Costs Page
=======================
Monitors all Snowflake AI/ML credit consumption:
 - Cortex LLM Functions (COMPLETE, SUMMARIZE, TRANSLATE, SENTIMENT, EMBED_TEXT, etc.)
 - Cortex Search (semantic search service)
 - ML Functions (Forecasting, Anomaly Detection, Classification, Regression)
 - Document AI (extract data from PDFs/images)
 - AI-related queries surfaced from Query History

Sources: CORTEX_FUNCTIONS_USAGE_HISTORY, CORTEX_SEARCH_SERVING_USAGE_HISTORY,
         ML_FUNCTIONS_USAGE_HISTORY, DOCUMENT_AI_USAGE_HISTORY, METERING_HISTORY
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from utils.snowflake_connector import run_query
from utils.queries import (
    AI_CORTEX_FUNCTIONS_DAILY,
    AI_CORTEX_FUNCTIONS_BY_MODEL,
    AI_CORTEX_FUNCTIONS_BY_USER,
    AI_CORTEX_FUNCTIONS_BY_WAREHOUSE,
    AI_CORTEX_SEARCH_DAILY,
    AI_CORTEX_SEARCH_BY_SERVICE,
    AI_CORTEX_VIA_METERING,
    AI_ML_FUNCTIONS_DAILY,
    AI_ML_FUNCTIONS_BY_USER,
    AI_DOCUMENT_AI_DAILY,
    AI_DOCUMENT_AI_BY_USER,
    AI_QUERIES_FROM_HISTORY,
    date_filter,
)

st.set_page_config(
    page_title="AI & Cortex Costs | Snowflake Monitor",
    page_icon="🤖",
    layout="wide",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🤖 AI & Cortex Costs")
    days = st.selectbox("Look-back period", [7, 14, 30, 60, 90], index=2,
                        format_func=lambda d: f"Last {d} days")
    credit_rate = st.number_input("Credit rate (USD)", 0.5, 50.0, 3.0, 0.25)
    st.markdown("---")
    st.caption("Sources: CORTEX_FUNCTIONS_USAGE_HISTORY,\nCORTEX_SEARCH_SERVING_USAGE_HISTORY,\nML_FUNCTIONS_USAGE_HISTORY,\nDOCUMENT_AI_USAGE_HISTORY")
    st.caption("Note: Cortex views require Snowflake Enterprise+ and the SNOWFLAKE DB privilege.")

DF = date_filter(days)

st.title("🤖 AI & Cortex Costs")
st.caption(f"Last {days} days · ${credit_rate:.2f}/credit")

st.info(
    "**Snowflake AI Features tracked here:**\n"
    "- **Cortex LLM Functions** — `COMPLETE`, `SUMMARIZE`, `TRANSLATE`, `SENTIMENT`, `EXTRACT_ANSWER`, `CLASSIFY_TEXT`, `EMBED_TEXT`\n"
    "- **Cortex Search** — Managed semantic search (vector index + serving)\n"
    "- **ML Functions** — `FORECAST`, `ANOMALY_DETECTION`, `CLASSIFICATION`, `REGRESSION`, `CONTRIBUTION_EXPLORER`\n"
    "- **Document AI** — Extract structured data from PDFs and images\n"
    "- **Cortex Analyst** — Text-to-SQL natural language queries"
)
st.markdown("---")

# ── KPI summary from METERING_HISTORY ────────────────────────────────────────
st.subheader("AI/Cortex Credit Overview")

with st.spinner("Loading AI credit overview…"):
    meter_df = run_query(AI_CORTEX_VIA_METERING.format(date_filter=DF))

if not meter_df.empty:
    meter_df.columns = [c.lower() for c in meter_df.columns]
    total_ai_metering = meter_df["credits_used"].sum()

    m1, m2 = st.columns(2)
    m1.metric("Total AI/ML Credits (via Metering)", f"{total_ai_metering:,.4f}")
    m1.caption(f"≈ ${total_ai_metering * credit_rate:,.2f}")
    m2.metric("AI Service Types", str(meter_df["service_type"].nunique()))

    fig = px.bar(
        meter_df.groupby("service_type")["credits_used"].sum().reset_index()
            .sort_values("credits_used", ascending=False),
        x="service_type", y="credits_used",
        title="AI/ML Credits by Service Type (from METERING_HISTORY)",
        color="credits_used", color_continuous_scale="Purples",
    )
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        coloraxis_showscale=False, xaxis_tickangle=-15,
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No AI/ML entries found in METERING_HISTORY for this period.")

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_llm, tab_search, tab_ml, tab_docai, tab_queries = st.tabs([
    "🧠 Cortex LLM Functions",
    "🔍 Cortex Search",
    "📊 ML Functions",
    "📄 Document AI",
    "🗂️ AI Queries in History",
])

# ═══════════════════════════════════════════════════════════════════════════════
# CORTEX LLM FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_llm:
    st.subheader("Cortex LLM Function Usage")
    st.caption(
        "Tracks calls to `SNOWFLAKE.CORTEX.COMPLETE`, `SUMMARIZE`, `TRANSLATE`, "
        "`SENTIMENT`, `EXTRACT_ANSWER`, `CLASSIFY_TEXT`, `EMBED_TEXT`, and more. "
        "Credits are consumed per token processed."
    )

    with st.spinner("Loading Cortex LLM data…"):
        llm_daily  = run_query(AI_CORTEX_FUNCTIONS_DAILY.format(date_filter=DF))
        llm_model  = run_query(AI_CORTEX_FUNCTIONS_BY_MODEL.format(date_filter=DF))
        llm_user   = run_query(AI_CORTEX_FUNCTIONS_BY_USER.format(date_filter=DF))
        llm_wh     = run_query(AI_CORTEX_FUNCTIONS_BY_WAREHOUSE.format(date_filter=DF))

    if llm_daily.empty:
        st.info("No Cortex LLM function usage found. `CORTEX_FUNCTIONS_USAGE_HISTORY` may be empty or unavailable on this account tier.")
    else:
        llm_daily.columns  = [c.lower() for c in llm_daily.columns]
        llm_model.columns  = [c.lower() for c in llm_model.columns]
        llm_user.columns   = [c.lower() for c in llm_user.columns]
        llm_wh.columns     = [c.lower() for c in llm_wh.columns]

        llm_daily["usage_date"] = pd.to_datetime(llm_daily["usage_date"])

        # KPIs
        total_llm_credits = llm_daily["credits_used"].sum()
        total_tokens       = llm_daily["total_tokens"].sum()
        total_calls        = llm_daily["call_count"].sum()

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total LLM Credits", f"{total_llm_credits:,.4f}")
        k1.caption(f"≈ ${total_llm_credits * credit_rate:,.2f}")
        k2.metric("Total Tokens", f"{total_tokens:,.0f}")
        k3.metric("Total Calls", f"{total_calls:,.0f}")
        k4.metric("Cost per 1K Tokens", f"${total_llm_credits * credit_rate / max(total_tokens, 1) * 1000:,.4f}" if total_tokens else "—")

        # Daily trend by function
        fig = px.bar(
            llm_daily,
            x="usage_date", y="credits_used",
            color="function_name",
            title="Daily LLM Credits by Function",
            labels={"credits_used": "Credits", "usage_date": "Date", "function_name": "Function"},
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, use_container_width=True)

        col1, col2 = st.columns(2)

        with col1:
            # By model
            if not llm_model.empty:
                fig2 = px.treemap(
                    llm_model, path=["model_name", "function_name"],
                    values="total_credits",
                    color="total_credits", color_continuous_scale="Purples",
                    title="Credits by Model & Function",
                )
                fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig2, use_container_width=True)

        with col2:
            # Tokens vs credits scatter by model
            if not llm_model.empty:
                fig3 = px.scatter(
                    llm_model,
                    x="total_tokens", y="total_credits",
                    color="model_name", size="call_count",
                    title="Tokens vs Credits by Model (bubble = call count)",
                    labels={"total_tokens": "Total Tokens", "total_credits": "Total Credits"},
                    hover_name="function_name",
                )
                fig3.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig3, use_container_width=True)

        # Model reference table
        st.subheader("Model Pricing Reference")
        model_pricing = pd.DataFrame({
            "Model": [
                "snowflake-arctic",
                "mistral-large",
                "mistral-large2",
                "mixtral-8x7b",
                "llama2-70b-chat",
                "llama3-8b",
                "llama3-70b",
                "llama3.1-8b",
                "llama3.1-70b",
                "llama3.1-405b",
                "reka-flash",
                "reka-core",
                "jamba-instruct",
                "jamba1.5-mini",
                "jamba1.5-large",
            ],
            "Credits / 1M Tokens (Input)": [
                0.6, 6.0, 6.0, 0.5, 0.5, 0.1, 0.5, 0.1, 0.5, 3.5, 1.0, 9.0, 1.0, 0.5, 3.5
            ],
            "Credits / 1M Tokens (Output)": [
                0.6, 18.0, 18.0, 1.5, 1.5, 0.3, 1.5, 0.3, 1.5, 10.5, 3.0, 27.0, 3.0, 0.7, 10.5
            ],
        })
        model_pricing["Est. Input $/1M"] = (model_pricing["Credits / 1M Tokens (Input)"] * credit_rate).map("${:.2f}".format)
        model_pricing["Est. Output $/1M"] = (model_pricing["Credits / 1M Tokens (Output)"] * credit_rate).map("${:.2f}".format)
        st.dataframe(model_pricing, use_container_width=True, hide_index=True)
        st.caption("Pricing as of early 2025. See [Snowflake docs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions#cost-considerations) for current rates.")

        # By user
        st.subheader("LLM Usage by User")
        if not llm_user.empty:
            fig4 = px.bar(
                llm_user.groupby("user_name")["total_credits"].sum().reset_index()
                    .sort_values("total_credits", ascending=False).head(20),
                x="user_name", y="total_credits",
                title="Top 20 Users by LLM Credits",
                color="total_credits", color_continuous_scale="Purples",
            )
            fig4.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                coloraxis_showscale=False, xaxis_tickangle=-30,
            )
            st.plotly_chart(fig4, use_container_width=True)
            st.dataframe(llm_user, use_container_width=True, hide_index=True)

        # By warehouse
        st.subheader("LLM Usage by Warehouse")
        if not llm_wh.empty:
            st.dataframe(llm_wh, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════════════════════
# CORTEX SEARCH
# ═══════════════════════════════════════════════════════════════════════════════
with tab_search:
    st.subheader("Cortex Search Usage")
    st.caption(
        "Cortex Search indexes your data as vectors and serves semantic search queries. "
        "Credits are consumed for both indexing (embedding) and serving (retrieval)."
    )

    with st.spinner("Loading Cortex Search data…"):
        cs_daily = run_query(AI_CORTEX_SEARCH_DAILY.format(date_filter=DF))
        cs_svc   = run_query(AI_CORTEX_SEARCH_BY_SERVICE.format(date_filter=DF))

    if cs_daily.empty:
        st.info("No Cortex Search usage found. `CORTEX_SEARCH_SERVING_USAGE_HISTORY` may be empty.")
    else:
        cs_daily.columns = [c.lower() for c in cs_daily.columns]
        cs_svc.columns   = [c.lower() for c in cs_svc.columns]
        cs_daily["usage_date"] = pd.to_datetime(cs_daily["usage_date"])

        total_cs_credits = cs_daily["credits_used"].sum()
        total_cs_queries = cs_daily["total_queries"].sum()

        k1, k2, k3 = st.columns(3)
        k1.metric("Total Search Credits", f"{total_cs_credits:,.4f}")
        k1.caption(f"≈ ${total_cs_credits * credit_rate:,.2f}")
        k2.metric("Total Search Queries Served", f"{total_cs_queries:,.0f}")
        k3.metric("Cost per 1K Queries", f"${total_cs_credits * credit_rate / max(total_cs_queries, 1) * 1000:,.4f}" if total_cs_queries else "—")

        # Daily trend by service
        fig = px.area(
            cs_daily, x="usage_date", y="credits_used",
            color="service_name",
            title="Daily Cortex Search Credits by Service",
        )
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

        # Queries served trend
        fig2 = px.bar(
            cs_daily.groupby("usage_date")["total_queries"].sum().reset_index(),
            x="usage_date", y="total_queries",
            title="Daily Search Queries Served",
            color_discrete_sequence=["#29B5E8"],
        )
        fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Per-Service Breakdown")
        st.dataframe(cs_svc, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════════════════════
# ML FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_ml:
    st.subheader("ML Functions Usage")
    st.caption(
        "Snowflake ML Functions provide no-code ML directly in SQL: "
        "`FORECAST`, `ANOMALY_DETECTION`, `CLASSIFICATION`, `REGRESSION`, "
        "`TOP_INSIGHTS`, `CONTRIBUTION_EXPLORER`."
    )

    with st.spinner("Loading ML function data…"):
        ml_daily = run_query(AI_ML_FUNCTIONS_DAILY.format(date_filter=DF))
        ml_user  = run_query(AI_ML_FUNCTIONS_BY_USER.format(date_filter=DF))

    if ml_daily.empty:
        st.info("No ML function usage found. `ML_FUNCTIONS_USAGE_HISTORY` may be empty.")
    else:
        ml_daily.columns = [c.lower() for c in ml_daily.columns]
        ml_user.columns  = [c.lower() for c in ml_user.columns]
        ml_daily["usage_date"] = pd.to_datetime(ml_daily["usage_date"])

        total_ml = ml_daily["credits_used"].sum()
        k1, k2 = st.columns(2)
        k1.metric("Total ML Credits", f"{total_ml:,.4f}")
        k1.caption(f"≈ ${total_ml * credit_rate:,.2f}")
        k2.metric("ML Function Types Used", str(ml_daily["function_name"].nunique()))

        col1, col2 = st.columns(2)

        with col1:
            fig = px.bar(
                ml_daily, x="usage_date", y="credits_used",
                color="function_name",
                title="Daily ML Function Credits by Function",
            )
            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fn_summary = ml_daily.groupby("function_name")[["credits_used", "call_count"]].sum().reset_index()
            fig2 = px.pie(
                fn_summary, names="function_name", values="credits_used",
                hole=0.4, title="Credits by ML Function",
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2, use_container_width=True)

        st.subheader("ML Usage by User")
        if not ml_user.empty:
            fig3 = px.bar(
                ml_user.sort_values("total_credits", ascending=False).head(20),
                x="user_name", y="total_credits",
                color="function_name",
                title="Top Users by ML Credits",
            )
            fig3.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                xaxis_tickangle=-30,
            )
            st.plotly_chart(fig3, use_container_width=True)
            st.dataframe(ml_user, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════════════════════
# DOCUMENT AI
# ═══════════════════════════════════════════════════════════════════════════════
with tab_docai:
    st.subheader("Document AI Usage")
    st.caption(
        "Document AI extracts structured data from unstructured documents (PDFs, images). "
        "Credits are consumed per page processed."
    )

    with st.spinner("Loading Document AI data…"):
        doc_daily = run_query(AI_DOCUMENT_AI_DAILY.format(date_filter=DF))
        doc_user  = run_query(AI_DOCUMENT_AI_BY_USER.format(date_filter=DF))

    if doc_daily.empty:
        st.info("No Document AI usage found. `DOCUMENT_AI_USAGE_HISTORY` may be empty.")
    else:
        doc_daily.columns = [c.lower() for c in doc_daily.columns]
        doc_user.columns  = [c.lower() for c in doc_user.columns]
        doc_daily["usage_date"] = pd.to_datetime(doc_daily["usage_date"])

        total_doc = doc_daily["credits_used"].sum()
        total_pages = doc_daily["pages_processed"].sum()

        k1, k2, k3 = st.columns(3)
        k1.metric("Total Document AI Credits", f"{total_doc:,.4f}")
        k1.caption(f"≈ ${total_doc * credit_rate:,.2f}")
        k2.metric("Total Pages Processed", f"{total_pages:,.0f}")
        k3.metric("Cost per Page", f"${total_doc * credit_rate / max(total_pages, 1):,.4f}" if total_pages else "—")

        col1, col2 = st.columns(2)

        with col1:
            fig = px.bar(
                doc_daily, x="usage_date", y="credits_used",
                color="model_name",
                title="Daily Document AI Credits by Model",
            )
            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig2 = px.line(
                doc_daily.groupby("usage_date")["pages_processed"].sum().reset_index(),
                x="usage_date", y="pages_processed",
                title="Daily Pages Processed", markers=True,
                color_discrete_sequence=["#44D7B6"],
            )
            fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Document AI Usage by User")
        if not doc_user.empty:
            st.dataframe(doc_user, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════════════════════
# AI QUERIES FROM QUERY HISTORY
# ═══════════════════════════════════════════════════════════════════════════════
with tab_queries:
    st.subheader("AI-Related Queries in Query History")
    st.caption(
        "Finds queries that called Snowflake Cortex or ML functions by scanning query text. "
        "Useful for attributing AI spend to specific users, warehouses, and applications."
    )

    with st.spinner("Scanning query history for AI calls…"):
        ai_qh = run_query(AI_QUERIES_FROM_HISTORY.format(date_filter=DF))

    if ai_qh.empty:
        st.info("No AI-related queries found in QUERY_HISTORY for this period.")
    else:
        ai_qh.columns = [c.lower() for c in ai_qh.columns]

        total_ai_cloud_credits = ai_qh["cloud_svc_credits"].sum()
        k1, k2, k3 = st.columns(3)
        k1.metric("AI Queries Found", f"{len(ai_qh):,}")
        k2.metric("Cloud Svc Credits (AI queries)", f"{total_ai_cloud_credits:,.4f}")
        k2.caption(f"≈ ${total_ai_cloud_credits * credit_rate:,.2f}")
        k3.metric("Avg Elapsed (sec)", f"{ai_qh['elapsed_sec'].mean():,.1f}" if "elapsed_sec" in ai_qh else "—")

        # By user
        col1, col2 = st.columns(2)
        with col1:
            by_user = ai_qh.groupby("user_name")["cloud_svc_credits"].sum().reset_index() \
                          .sort_values("cloud_svc_credits", ascending=False).head(15)
            fig = px.bar(
                by_user, x="user_name", y="cloud_svc_credits",
                title="Top Users — AI Query Cloud Svc Credits",
                color="cloud_svc_credits", color_continuous_scale="Purples",
            )
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                coloraxis_showscale=False, xaxis_tickangle=-30,
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            by_wh = ai_qh.groupby("warehouse_name")["cloud_svc_credits"].sum().reset_index() \
                        .sort_values("cloud_svc_credits", ascending=False).head(15)
            fig2 = px.bar(
                by_wh, x="warehouse_name", y="cloud_svc_credits",
                title="Top Warehouses — AI Query Cloud Svc Credits",
                color="cloud_svc_credits", color_continuous_scale="Blues",
            )
            fig2.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                coloraxis_showscale=False, xaxis_tickangle=-30,
            )
            st.plotly_chart(fig2, use_container_width=True)

        # Full table with query text viewer
        show_cols = ["query_id", "user_name", "warehouse_name", "elapsed_sec",
                     "cloud_svc_credits", "start_time"]
        avail_cols = [c for c in show_cols if c in ai_qh.columns]
        st.dataframe(ai_qh[avail_cols], use_container_width=True, hide_index=True)

        st.subheader("Query Text Viewer")
        if "query_id" in ai_qh.columns and "query_text" in ai_qh.columns:
            sel_qid = st.selectbox("Select Query ID", ai_qh["query_id"].tolist()[:30])
            if sel_qid:
                row = ai_qh[ai_qh["query_id"] == sel_qid].iloc[0]
                st.code(row.get("query_text", "N/A"), language="sql")
