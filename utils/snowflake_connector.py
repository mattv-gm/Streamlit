"""Snowflake connection management using st.connection or direct connector."""

import os
import streamlit as st
import snowflake.connector
from snowflake.connector import DictCursor
import pandas as pd
from typing import Optional


def get_connection_params() -> dict:
    """Build connection params from st.secrets or environment variables."""
    # Try st.secrets first (for deployed apps)
    try:
        params = {
            "account": st.secrets["snowflake"]["account"],
            "user": st.secrets["snowflake"]["user"],
            "password": st.secrets["snowflake"].get("password", ""),
            "warehouse": st.secrets["snowflake"].get("warehouse", ""),
            "database": st.secrets["snowflake"].get("database", "SNOWFLAKE"),
            "schema": st.secrets["snowflake"].get("schema", "ACCOUNT_USAGE"),
            "role": st.secrets["snowflake"].get("role", "ACCOUNTADMIN"),
        }
        # Support private key auth
        if "private_key_path" in st.secrets["snowflake"]:
            params["private_key_path"] = st.secrets["snowflake"]["private_key_path"]
            params.pop("password", None)
        return params
    except Exception:
        pass

    # Fall back to environment variables
    params = {
        "account": os.getenv("SNOWFLAKE_ACCOUNT", ""),
        "user": os.getenv("SNOWFLAKE_USER", ""),
        "password": os.getenv("SNOWFLAKE_PASSWORD", ""),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", ""),
        "database": os.getenv("SNOWFLAKE_DATABASE", "SNOWFLAKE"),
        "schema": os.getenv("SNOWFLAKE_SCHEMA", "ACCOUNT_USAGE"),
        "role": os.getenv("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
    }
    return params


@st.cache_resource(ttl=3600, show_spinner=False)
def get_snowflake_connection():
    """Create and cache a Snowflake connection."""
    params = get_connection_params()
    conn_params = {k: v for k, v in params.items() if v}
    conn = snowflake.connector.connect(**conn_params)
    return conn


def run_query(sql: str, ttl: int = 300) -> pd.DataFrame:
    """Execute a SQL query and return a DataFrame. Results cached by TTL seconds."""
    @st.cache_data(ttl=ttl, show_spinner=False)
    def _run(query: str) -> pd.DataFrame:
        conn = get_snowflake_connection()
        cur = conn.cursor(DictCursor)
        try:
            cur.execute(query)
            rows = cur.fetchall()
            if rows:
                return pd.DataFrame(rows)
            return pd.DataFrame()
        finally:
            cur.close()
    return _run(sql)


def test_connection() -> tuple[bool, str]:
    """Test Snowflake connectivity. Returns (success, message)."""
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        cur.execute("SELECT CURRENT_ACCOUNT(), CURRENT_REGION(), CURRENT_ROLE()")
        row = cur.fetchone()
        cur.close()
        return True, f"Connected: account={row[0]}, region={row[1]}, role={row[2]}"
    except Exception as e:
        return False, str(e)


def format_credits(value: Optional[float]) -> str:
    """Format a credit value for display."""
    if value is None:
        return "—"
    return f"{value:,.2f}"


def format_dollars(value: Optional[float], rate: float = 3.0) -> str:
    """Estimate cost in USD given a credit rate (default $3/credit)."""
    if value is None:
        return "—"
    return f"${value * rate:,.2f}"


def format_bytes(value: Optional[float]) -> str:
    """Format bytes into human-readable storage string."""
    if value is None:
        return "—"
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if abs(value) < 1024.0:
            return f"{value:,.2f} {unit}"
        value /= 1024.0
    return f"{value:,.2f} PB"
