# ❄️ Snowflake Cost Monitor

A comprehensive multi-page Streamlit app for monitoring all cost dimensions in Snowflake — compute, storage, queries, serverless services, data transfer, and warehouse efficiency.

## Pages

| Page | Description |
|------|-------------|
| **Overview** | Account-level KPIs, daily credit trends, service breakdown, resource monitors |
| **💻 Compute Costs** | Warehouse credit usage, daily/hourly trends, cloud-services adjustment, warehouse config |
| **🗄️ Storage Costs** | DB/Stage/Failsafe/Time-Travel storage, per-database and per-table breakdown |
| **🔍 Query Analysis** | Expensive queries, user/warehouse cost attribution, failures, data spill |
| **⚙️ Serverless & Cloud Services** | Snowpipe, Tasks, Materialized Views, Auto-Clustering, Search Optimization, Replication |
| **🏭 Warehouse Efficiency** | Idle analysis, queuing, query duration distribution, sizing tips, data transfer, login activity |

## Setup

### 1. Clone & install dependencies

```bash
git clone <repo>
cd Streamlit
pip install -r requirements.txt
```

### 2. Configure Snowflake credentials

Copy the secrets template and fill in your account details:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit .streamlit/secrets.toml with your credentials
```

Or set environment variables:

```bash
export SNOWFLAKE_ACCOUNT="abc12345.us-east-1"
export SNOWFLAKE_USER="your_user"
export SNOWFLAKE_PASSWORD="your_password"
export SNOWFLAKE_ROLE="ACCOUNTADMIN"
export SNOWFLAKE_DATABASE="SNOWFLAKE"
export SNOWFLAKE_SCHEMA="ACCOUNT_USAGE"
```

### 3. Run the app

```bash
streamlit run app.py
```

## Required Permissions

The connecting role needs access to `SNOWFLAKE.ACCOUNT_USAGE` views:

```sql
-- Grant ACCOUNT_USAGE access to a role
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE your_role;
```

The `ACCOUNTADMIN` role has this by default.

## Data Latency

Most `ACCOUNT_USAGE` views have a **3-hour latency**. `QUERY_HISTORY` can be up to 45 minutes. `STORAGE_USAGE` is daily.

## Cost Dimensions Monitored

- **Compute** — Virtual warehouse credits (compute + cloud services adjustment)
- **Storage** — Active, Time Travel, Failsafe, Clone, Stage
- **Cloud Services** — Metadata operations, query compilation, auth
- **Serverless** — Snowpipe, Tasks, Materialized View refreshes, Auto-Clustering, Search Optimization, Replication
- **Data Transfer** — Cross-region and cross-cloud egress
- **Query Costs** — Per-query elapsed time, bytes scanned, spill, user attribution
- **Warehouse Efficiency** — Utilization %, idle time, queue time, sizing guidance
- **Resource Monitors** — Credit quota utilization and alert thresholds
