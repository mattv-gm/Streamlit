"""
All SQL queries for Snowflake cost monitoring.
Sources: SNOWFLAKE.ACCOUNT_USAGE and SNOWFLAKE.ORGANIZATION_USAGE views.
Requires ACCOUNTADMIN or SNOWFLAKE database privileges.
"""

# ─── Date range helper ────────────────────────────────────────────────────────

def date_filter(days: int, col: str = "start_time") -> str:
    return f"{col} >= DATEADD('day', -{days}, CURRENT_TIMESTAMP())"


# ═══════════════════════════════════════════════════════════════════════════════
# OVERVIEW / SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

OVERVIEW_TOTAL_CREDITS = """
SELECT
    ROUND(SUM(credits_used_compute), 2)         AS compute_credits,
    ROUND(SUM(credits_used_cloud_services), 2)  AS cloud_svc_credits,
    ROUND(SUM(credits_used), 2)                 AS total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
WHERE {date_filter}
"""

OVERVIEW_DAILY_CREDITS = """
SELECT
    DATE_TRUNC('day', start_time)               AS usage_date,
    service_type,
    ROUND(SUM(credits_used_compute), 4)         AS compute_credits,
    ROUND(SUM(credits_used_cloud_services), 4)  AS cloud_svc_credits,
    ROUND(SUM(credits_used), 4)                 AS total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
WHERE {date_filter}
GROUP BY 1, 2
ORDER BY 1 DESC, 2
"""

OVERVIEW_CREDITS_BY_SERVICE = """
SELECT
    service_type,
    ROUND(SUM(credits_used_compute), 2)         AS compute_credits,
    ROUND(SUM(credits_used_cloud_services), 2)  AS cloud_svc_credits,
    ROUND(SUM(credits_used), 2)                 AS total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
WHERE {date_filter}
GROUP BY 1
ORDER BY 4 DESC
"""

OVERVIEW_STORAGE_TOTAL = """
SELECT
    ROUND(AVG(storage_bytes) / POWER(1024,4), 4)           AS avg_database_tb,
    ROUND(AVG(stage_bytes) / POWER(1024,4), 4)             AS avg_stage_tb,
    ROUND(AVG(failsafe_bytes) / POWER(1024,4), 4)          AS avg_failsafe_tb,
    ROUND((AVG(storage_bytes) + AVG(stage_bytes) + AVG(failsafe_bytes)) / POWER(1024,4), 4) AS avg_total_tb
FROM SNOWFLAKE.ACCOUNT_USAGE.STORAGE_USAGE
WHERE {date_filter}
"""


# ═══════════════════════════════════════════════════════════════════════════════
# COMPUTE COSTS
# ═══════════════════════════════════════════════════════════════════════════════

COMPUTE_BY_WAREHOUSE = """
SELECT
    warehouse_name,
    ROUND(SUM(credits_used_compute), 2)         AS compute_credits,
    ROUND(SUM(credits_used_cloud_services), 2)  AS cloud_svc_credits,
    ROUND(SUM(credits_used), 2)                 AS total_credits,
    COUNT(DISTINCT DATE_TRUNC('day', start_time)) AS active_days
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE {date_filter}
GROUP BY 1
ORDER BY 4 DESC
"""

COMPUTE_DAILY_BY_WAREHOUSE = """
SELECT
    DATE_TRUNC('day', start_time)   AS usage_date,
    warehouse_name,
    ROUND(SUM(credits_used), 4)     AS total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE {date_filter}
GROUP BY 1, 2
ORDER BY 1 DESC, 3 DESC
"""

COMPUTE_HOURLY_TREND = """
SELECT
    DATE_TRUNC('hour', start_time)  AS usage_hour,
    ROUND(SUM(credits_used), 4)     AS total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE {date_filter}
GROUP BY 1
ORDER BY 1 DESC
"""

COMPUTE_WAREHOUSE_SIZES = """
SELECT
    w.size                          AS warehouse_size,
    COUNT(DISTINCT wmh.warehouse_name) AS warehouse_count,
    ROUND(SUM(wmh.credits_used), 2) AS total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY wmh
JOIN SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSES w
    ON wmh.warehouse_name = w.name
WHERE {date_filter}
GROUP BY 1
ORDER BY 3 DESC
"""

COMPUTE_CLOUD_SERVICES_ADJUSTMENT = """
SELECT
    DATE_TRUNC('day', start_time)                                   AS usage_date,
    ROUND(SUM(credits_used_cloud_services), 4)                      AS cloud_svc_credits,
    ROUND(SUM(credits_adjustment_cloud_services), 4)                AS cloud_svc_adjustment,
    ROUND(SUM(credits_used_cloud_services)
          + SUM(credits_adjustment_cloud_services), 4)              AS net_cloud_svc_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
WHERE {date_filter}
GROUP BY 1
ORDER BY 1 DESC
"""


# ═══════════════════════════════════════════════════════════════════════════════
# STORAGE COSTS
# ═══════════════════════════════════════════════════════════════════════════════

STORAGE_DAILY = """
SELECT
    USAGE_DATE,
    ROUND(storage_bytes / POWER(1024,3), 2)     AS database_gb,
    ROUND(stage_bytes / POWER(1024,3), 2)       AS stage_gb,
    ROUND(failsafe_bytes / POWER(1024,3), 2)    AS failsafe_gb,
    ROUND((storage_bytes + stage_bytes + failsafe_bytes) / POWER(1024,3), 2) AS total_gb
FROM SNOWFLAKE.ACCOUNT_USAGE.STORAGE_USAGE
WHERE {date_filter}
ORDER BY 1 DESC
"""

STORAGE_BY_DATABASE = """
SELECT
    TABLE_CATALOG                                       AS database_name,
    ROUND(SUM(ACTIVE_BYTES) / POWER(1024,3), 4)        AS active_gb,
    ROUND(SUM(TIME_TRAVEL_BYTES) / POWER(1024,3), 4)   AS time_travel_gb,
    ROUND(SUM(FAILSAFE_BYTES) / POWER(1024,3), 4)      AS failsafe_gb,
    ROUND(SUM(RETAINED_FOR_CLONE_BYTES) / POWER(1024,3), 4) AS clone_gb,
    ROUND(SUM(ACTIVE_BYTES + TIME_TRAVEL_BYTES + FAILSAFE_BYTES + RETAINED_FOR_CLONE_BYTES) / POWER(1024,3), 4) AS total_gb
FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS
WHERE DELETED = FALSE
GROUP BY 1
ORDER BY 6 DESC
LIMIT 50
"""

STORAGE_BY_TABLE_TOP = """
SELECT
    TABLE_CATALOG       AS database_name,
    TABLE_SCHEMA        AS schema_name,
    TABLE_NAME,
    TABLE_TYPE,
    ROUND(ACTIVE_BYTES / POWER(1024,3), 4)          AS active_gb,
    ROUND(TIME_TRAVEL_BYTES / POWER(1024,3), 4)     AS time_travel_gb,
    ROUND(FAILSAFE_BYTES / POWER(1024,3), 4)        AS failsafe_gb,
    ROUND((ACTIVE_BYTES + TIME_TRAVEL_BYTES + FAILSAFE_BYTES) / POWER(1024,3), 4) AS total_gb
FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS
WHERE DELETED = FALSE
ORDER BY 8 DESC
LIMIT 100
"""

STORAGE_STAGE_USAGE = """
SELECT
    STAGE_CATALOG   AS database_name,
    STAGE_SCHEMA    AS schema_name,
    STAGE_NAME,
    STAGE_TYPE,
    STAGE_URL,
    ROUND(STAGE_BYTES / POWER(1024,3), 4)  AS stage_gb
FROM SNOWFLAKE.ACCOUNT_USAGE.STAGES
WHERE DELETED IS NULL
ORDER BY 6 DESC
LIMIT 100
"""


# ═══════════════════════════════════════════════════════════════════════════════
# QUERY ANALYSIS (Cost per Query)
# ═══════════════════════════════════════════════════════════════════════════════

QUERY_TOP_EXPENSIVE = """
SELECT
    query_id,
    query_text,
    user_name,
    warehouse_name,
    warehouse_size,
    database_name,
    schema_name,
    execution_status,
    ROUND(total_elapsed_time / 1000, 1)             AS elapsed_sec,
    ROUND(execution_time / 1000, 1)                 AS execution_sec,
    ROUND(queued_overload_time / 1000, 1)           AS queued_overload_sec,
    bytes_scanned,
    rows_produced,
    ROUND(credits_used_cloud_services, 6)           AS cloud_svc_credits,
    ROUND(bytes_scanned / POWER(1024,3), 4)         AS gb_scanned,
    start_time
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE {date_filter}
  AND execution_status = 'SUCCESS'
  AND total_elapsed_time > 0
ORDER BY total_elapsed_time DESC
LIMIT 100
"""

QUERY_CREDITS_BY_USER = """
SELECT
    user_name,
    COUNT(*)                                        AS query_count,
    ROUND(SUM(credits_used_cloud_services), 4)      AS cloud_svc_credits,
    ROUND(AVG(total_elapsed_time) / 1000, 2)        AS avg_elapsed_sec,
    ROUND(SUM(bytes_scanned) / POWER(1024,4), 4)    AS total_tb_scanned,
    ROUND(MAX(total_elapsed_time) / 1000, 1)        AS max_elapsed_sec
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE {date_filter}
  AND execution_status = 'SUCCESS'
GROUP BY 1
ORDER BY 3 DESC
LIMIT 50
"""

QUERY_CREDITS_BY_WAREHOUSE = """
SELECT
    warehouse_name,
    COUNT(*)                                        AS query_count,
    ROUND(SUM(credits_used_cloud_services), 4)      AS cloud_svc_credits,
    ROUND(AVG(total_elapsed_time) / 1000, 2)        AS avg_elapsed_sec,
    ROUND(SUM(bytes_scanned) / POWER(1024,4), 4)    AS total_tb_scanned
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE {date_filter}
  AND execution_status = 'SUCCESS'
GROUP BY 1
ORDER BY 3 DESC
LIMIT 30
"""

QUERY_FAILED_COSTLY = """
SELECT
    user_name,
    warehouse_name,
    error_code,
    error_message,
    COUNT(*)                                        AS failure_count,
    ROUND(AVG(total_elapsed_time) / 1000, 2)        AS avg_elapsed_sec,
    ROUND(SUM(credits_used_cloud_services), 6)      AS total_cloud_svc_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE {date_filter}
  AND execution_status != 'SUCCESS'
GROUP BY 1, 2, 3, 4
ORDER BY 5 DESC
LIMIT 50
"""

QUERY_VOLUME_TREND = """
SELECT
    DATE_TRUNC('day', start_time)   AS query_date,
    execution_status,
    COUNT(*)                        AS query_count,
    ROUND(AVG(total_elapsed_time) / 1000, 2) AS avg_elapsed_sec,
    ROUND(SUM(bytes_scanned) / POWER(1024,4), 4) AS total_tb_scanned
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE {date_filter}
GROUP BY 1, 2
ORDER BY 1 DESC
"""

QUERY_BYTES_SPILLED = """
SELECT
    DATE_TRUNC('day', start_time)                   AS query_date,
    ROUND(SUM(bytes_spilled_to_local_storage) / POWER(1024,3), 2)  AS local_spill_gb,
    ROUND(SUM(bytes_spilled_to_remote_storage) / POWER(1024,3), 2) AS remote_spill_gb
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE {date_filter}
GROUP BY 1
ORDER BY 1 DESC
"""


# ═══════════════════════════════════════════════════════════════════════════════
# WAREHOUSE EFFICIENCY
# ═══════════════════════════════════════════════════════════════════════════════

WAREHOUSE_EFFICIENCY = """
SELECT
    warehouse_name,
    COUNT(*)                                            AS session_count,
    ROUND(AVG(elapsed_time) / 1000, 1)                 AS avg_elapsed_sec,
    ROUND(SUM(CASE WHEN execution_status = 'SUCCESS' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS success_pct,
    ROUND(AVG(queued_overload_time) / 1000, 2)         AS avg_overload_queue_sec,
    ROUND(AVG(queued_provisioning_time) / 1000, 2)     AS avg_provision_queue_sec,
    ROUND(SUM(bytes_scanned) / NULLIF(SUM(bytes_processed), 0) * 100, 1) AS scan_ratio_pct
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE {date_filter}
GROUP BY 1
ORDER BY 1
"""

WAREHOUSE_IDLE_ANALYSIS = """
WITH warehouse_hours AS (
    SELECT
        warehouse_name,
        DATE_TRUNC('hour', start_time)  AS usage_hour,
        SUM(credits_used)               AS credits_used
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE {date_filter}
    GROUP BY 1, 2
)
SELECT
    warehouse_name,
    COUNT(*)                            AS total_hours,
    SUM(CASE WHEN credits_used > 0 THEN 1 ELSE 0 END) AS active_hours,
    COUNT(*) - SUM(CASE WHEN credits_used > 0 THEN 1 ELSE 0 END) AS idle_hours,
    ROUND(SUM(CASE WHEN credits_used > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS utilization_pct,
    ROUND(SUM(credits_used), 2)        AS total_credits
FROM warehouse_hours
GROUP BY 1
ORDER BY 5 ASC
"""

WAREHOUSE_SETTINGS = """
SELECT
    name            AS warehouse_name,
    type,
    size,
    min_cluster_count,
    max_cluster_count,
    scaling_policy,
    auto_suspend,
    auto_resume,
    resource_monitor,
    owner,
    created_on
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSES
WHERE deleted IS NULL
ORDER BY name
"""

WAREHOUSE_QUERY_DISTRIBUTION = """
SELECT
    warehouse_name,
    warehouse_size,
    ROUND(SUM(CASE WHEN total_elapsed_time < 1000 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1)  AS pct_under_1s,
    ROUND(SUM(CASE WHEN total_elapsed_time BETWEEN 1000 AND 10000 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS pct_1_10s,
    ROUND(SUM(CASE WHEN total_elapsed_time BETWEEN 10000 AND 60000 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS pct_10_60s,
    ROUND(SUM(CASE WHEN total_elapsed_time > 60000 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1)  AS pct_over_60s,
    COUNT(*) AS total_queries
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE {date_filter}
  AND warehouse_name IS NOT NULL
GROUP BY 1, 2
ORDER BY 7 DESC
LIMIT 30
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SERVERLESS & CLOUD SERVICES
# ═══════════════════════════════════════════════════════════════════════════════

SERVERLESS_CREDITS = """
SELECT
    service_type,
    ROUND(SUM(credits_used), 4)     AS total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
WHERE service_type NOT IN ('VIRTUAL_WAREHOUSE', 'CLOUD_SERVICES')
  AND {date_filter}
GROUP BY 1
ORDER BY 2 DESC
"""

SNOWPIPE_COSTS = """
SELECT
    pipe_name,
    DATE_TRUNC('day', start_time)       AS usage_date,
    ROUND(SUM(credits_used), 6)         AS credits_used,
    ROUND(SUM(bytes_inserted) / POWER(1024,3), 4) AS gb_inserted,
    SUM(files_inserted)                 AS files_inserted
FROM SNOWFLAKE.ACCOUNT_USAGE.PIPE_USAGE_HISTORY
WHERE {date_filter}
GROUP BY 1, 2
ORDER BY 1, 2 DESC
"""

TASK_COSTS = """
SELECT
    DATABASE_NAME,
    SCHEMA_NAME,
    TASK_NAME,
    COUNT(*)                            AS run_count,
    SUM(CASE WHEN STATE = 'SUCCEEDED' THEN 1 ELSE 0 END) AS success_count,
    SUM(CASE WHEN STATE = 'FAILED' THEN 1 ELSE 0 END)    AS failure_count,
    ROUND(SUM(CREDITS_USED_CLOUD_SERVICES), 6)           AS cloud_svc_credits,
    ROUND(AVG(SCHEDULED_TIME::NUMBER - COMPLETED_TIME::NUMBER) / 1000, 1) AS avg_run_ms
FROM SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY
WHERE {date_filter}
GROUP BY 1, 2, 3
ORDER BY 7 DESC
LIMIT 50
"""

REPLICATION_COSTS = """
SELECT
    database_name,
    DATE_TRUNC('day', start_time)   AS replication_date,
    ROUND(SUM(credits_used), 4)     AS credits_used,
    ROUND(SUM(bytes_transferred) / POWER(1024,3), 4) AS gb_transferred
FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASE_REPLICATION_USAGE_HISTORY
WHERE {date_filter}
GROUP BY 1, 2
ORDER BY 3 DESC
"""

SEARCH_OPTIMIZATION_COSTS = """
SELECT
    database_name,
    schema_name,
    table_name,
    DATE_TRUNC('day', start_time)   AS usage_date,
    ROUND(SUM(credits_used), 6)     AS credits_used,
    ROUND(SUM(num_bytes_added) / POWER(1024,3), 4) AS gb_added
FROM SNOWFLAKE.ACCOUNT_USAGE.SEARCH_OPTIMIZATION_HISTORY
WHERE {date_filter}
GROUP BY 1, 2, 3, 4
ORDER BY 5 DESC
LIMIT 50
"""

MATERIALIZED_VIEW_COSTS = """
SELECT
    database_name,
    schema_name,
    table_name,
    DATE_TRUNC('day', start_time)   AS usage_date,
    ROUND(SUM(credits_used), 6)     AS credits_used,
    ROUND(SUM(bytes_refreshed) / POWER(1024,3), 4) AS gb_refreshed
FROM SNOWFLAKE.ACCOUNT_USAGE.MATERIALIZED_VIEW_REFRESH_HISTORY
WHERE {date_filter}
GROUP BY 1, 2, 3, 4
ORDER BY 5 DESC
LIMIT 50
"""

CLUSTERING_COSTS = """
SELECT
    database_name,
    schema_name,
    table_name,
    DATE_TRUNC('day', start_time)   AS usage_date,
    ROUND(SUM(credits_used), 6)     AS credits_used,
    ROUND(SUM(num_bytes_reclustered) / POWER(1024,3), 4) AS gb_reclustered
FROM SNOWFLAKE.ACCOUNT_USAGE.AUTOMATIC_CLUSTERING_HISTORY
WHERE {date_filter}
GROUP BY 1, 2, 3, 4
ORDER BY 5 DESC
LIMIT 50
"""


# ═══════════════════════════════════════════════════════════════════════════════
# DATA TRANSFER COSTS
# ═══════════════════════════════════════════════════════════════════════════════

DATA_TRANSFER_DAILY = """
SELECT
    DATE_TRUNC('day', start_time)               AS transfer_date,
    transfer_type,
    source_cloud,
    source_region,
    target_cloud,
    target_region,
    ROUND(SUM(bytes_transferred) / POWER(1024,3), 4) AS gb_transferred
FROM SNOWFLAKE.ACCOUNT_USAGE.DATA_TRANSFER_HISTORY
WHERE {date_filter}
GROUP BY 1, 2, 3, 4, 5, 6
ORDER BY 1 DESC, 7 DESC
"""

DATA_TRANSFER_BY_DIRECTION = """
SELECT
    transfer_type,
    source_cloud   || ' / ' || source_region    AS source,
    target_cloud   || ' / ' || target_region    AS target,
    ROUND(SUM(bytes_transferred) / POWER(1024,3), 4) AS gb_transferred
FROM SNOWFLAKE.ACCOUNT_USAGE.DATA_TRANSFER_HISTORY
WHERE {date_filter}
GROUP BY 1, 2, 3
ORDER BY 4 DESC
"""


# ═══════════════════════════════════════════════════════════════════════════════
# RESOURCE MONITORS
# ═══════════════════════════════════════════════════════════════════════════════

RESOURCE_MONITORS = """
SELECT
    name                AS monitor_name,
    frequency,
    credit_quota,
    ROUND(credits_used, 2)  AS credits_used,
    ROUND(credits_used / NULLIF(credit_quota, 0) * 100, 1) AS usage_pct,
    notify_at,
    suspend_at,
    suspend_immediately_at,
    start_time,
    end_time,
    owner
FROM SNOWFLAKE.ACCOUNT_USAGE.RESOURCE_MONITORS
WHERE deleted IS NULL
ORDER BY usage_pct DESC NULLS LAST
"""


# ═══════════════════════════════════════════════════════════════════════════════
# USER & ROLE ACTIVITY
# ═══════════════════════════════════════════════════════════════════════════════

LOGIN_ACTIVITY = """
SELECT
    user_name,
    COUNT(*)                                AS total_logins,
    SUM(CASE WHEN is_success = 'YES' THEN 1 ELSE 0 END) AS successful_logins,
    SUM(CASE WHEN is_success = 'NO'  THEN 1 ELSE 0 END) AS failed_logins,
    MAX(event_timestamp)                    AS last_login
FROM SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY
WHERE {date_filter}
GROUP BY 1
ORDER BY 2 DESC
LIMIT 50
"""

USER_CREDIT_CONSUMPTION = """
SELECT
    qh.user_name,
    COUNT(*)                                        AS query_count,
    ROUND(SUM(qh.credits_used_cloud_services), 4)  AS cloud_svc_credits,
    ROUND(SUM(wmh.credits_used), 4)                AS warehouse_credits,
    ROUND(AVG(qh.total_elapsed_time) / 1000, 2)    AS avg_query_sec,
    ROUND(SUM(qh.bytes_scanned) / POWER(1024,4), 4) AS total_tb_scanned
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY qh
LEFT JOIN SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY wmh
    ON qh.warehouse_name = wmh.warehouse_name
    AND DATE_TRUNC('hour', qh.start_time) = DATE_TRUNC('hour', wmh.start_time)
WHERE qh.{date_filter}
GROUP BY 1
ORDER BY 4 DESC NULLS LAST
LIMIT 50
"""


# ═══════════════════════════════════════════════════════════════════════════════
# AI / CORTEX SERVICES
# ═══════════════════════════════════════════════════════════════════════════════

# ── Cortex LLM Functions (COMPLETE, SUMMARIZE, TRANSLATE, SENTIMENT, etc.) ───

AI_CORTEX_FUNCTIONS_DAILY = """
SELECT
    DATE_TRUNC('day', start_time)           AS usage_date,
    function_name,
    model_name,
    ROUND(SUM(credits_used), 6)             AS credits_used,
    SUM(token_count)                        AS total_tokens,
    COUNT(*)                                AS call_count
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
WHERE {date_filter}
GROUP BY 1, 2, 3
ORDER BY 1 DESC, 4 DESC
"""

AI_CORTEX_FUNCTIONS_BY_MODEL = """
SELECT
    model_name,
    function_name,
    ROUND(SUM(credits_used), 4)             AS total_credits,
    SUM(token_count)                        AS total_tokens,
    COUNT(*)                                AS call_count,
    ROUND(AVG(token_count), 0)              AS avg_tokens_per_call
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
WHERE {date_filter}
GROUP BY 1, 2
ORDER BY 3 DESC
"""

AI_CORTEX_FUNCTIONS_BY_USER = """
SELECT
    user_name,
    model_name,
    function_name,
    ROUND(SUM(credits_used), 4)             AS total_credits,
    SUM(token_count)                        AS total_tokens,
    COUNT(*)                                AS call_count
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
WHERE {date_filter}
GROUP BY 1, 2, 3
ORDER BY 4 DESC
LIMIT 50
"""

AI_CORTEX_FUNCTIONS_BY_WAREHOUSE = """
SELECT
    warehouse_name,
    model_name,
    function_name,
    ROUND(SUM(credits_used), 4)             AS total_credits,
    SUM(token_count)                        AS total_tokens,
    COUNT(*)                                AS call_count
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
WHERE {date_filter}
GROUP BY 1, 2, 3
ORDER BY 4 DESC
LIMIT 50
"""

# ── Cortex Search ─────────────────────────────────────────────────────────────

AI_CORTEX_SEARCH_DAILY = """
SELECT
    DATE_TRUNC('day', start_time)           AS usage_date,
    service_name,
    ROUND(SUM(credits_used), 6)             AS credits_used,
    SUM(num_queries)                        AS total_queries,
    SUM(num_rows_indexed)                   AS rows_indexed
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY
WHERE {date_filter}
GROUP BY 1, 2
ORDER BY 1 DESC, 3 DESC
"""

AI_CORTEX_SEARCH_BY_SERVICE = """
SELECT
    service_name,
    database_name,
    schema_name,
    ROUND(SUM(credits_used), 4)             AS total_credits,
    SUM(num_queries)                        AS total_queries,
    SUM(num_rows_indexed)                   AS total_rows_indexed,
    ROUND(AVG(num_queries), 1)              AS avg_daily_queries
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_SERVING_USAGE_HISTORY
WHERE {date_filter}
GROUP BY 1, 2, 3
ORDER BY 4 DESC
"""

# ── Cortex Analyst (Text-to-SQL) ──────────────────────────────────────────────
# Note: Billed via cloud services credits; surfaced through METERING_HISTORY

AI_CORTEX_VIA_METERING = """
SELECT
    DATE_TRUNC('day', start_time)           AS usage_date,
    service_type,
    ROUND(SUM(credits_used), 6)             AS credits_used
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
WHERE (
    service_type ILIKE '%CORTEX%'
    OR service_type ILIKE '%AI%'
    OR service_type ILIKE '%ML%'
    OR service_type ILIKE '%DOCUMENT%'
)
  AND {date_filter}
GROUP BY 1, 2
ORDER BY 1 DESC, 3 DESC
"""

# ── ML Functions (Forecasting, Anomaly Detection, Classification, etc.) ───────

AI_ML_FUNCTIONS_DAILY = """
SELECT
    DATE_TRUNC('day', start_time)           AS usage_date,
    function_name,
    ROUND(SUM(credits_used), 6)             AS credits_used,
    COUNT(*)                                AS call_count
FROM SNOWFLAKE.ACCOUNT_USAGE.ML_FUNCTIONS_USAGE_HISTORY
WHERE {date_filter}
GROUP BY 1, 2
ORDER BY 1 DESC, 3 DESC
"""

AI_ML_FUNCTIONS_BY_USER = """
SELECT
    user_name,
    function_name,
    ROUND(SUM(credits_used), 4)             AS total_credits,
    COUNT(*)                                AS call_count
FROM SNOWFLAKE.ACCOUNT_USAGE.ML_FUNCTIONS_USAGE_HISTORY
WHERE {date_filter}
GROUP BY 1, 2
ORDER BY 3 DESC
LIMIT 50
"""

# ── Document AI ───────────────────────────────────────────────────────────────

AI_DOCUMENT_AI_DAILY = """
SELECT
    DATE_TRUNC('day', start_time)           AS usage_date,
    model_name,
    ROUND(SUM(credits_used), 6)             AS credits_used,
    SUM(num_pages_processed)                AS pages_processed,
    COUNT(*)                                AS call_count
FROM SNOWFLAKE.ACCOUNT_USAGE.DOCUMENT_AI_USAGE_HISTORY
WHERE {date_filter}
GROUP BY 1, 2
ORDER BY 1 DESC, 3 DESC
"""

AI_DOCUMENT_AI_BY_USER = """
SELECT
    user_name,
    model_name,
    ROUND(SUM(credits_used), 4)             AS total_credits,
    SUM(num_pages_processed)                AS total_pages,
    COUNT(*)                                AS call_count,
    ROUND(SUM(credits_used) / NULLIF(SUM(num_pages_processed), 0), 6) AS credits_per_page
FROM SNOWFLAKE.ACCOUNT_USAGE.DOCUMENT_AI_USAGE_HISTORY
WHERE {date_filter}
GROUP BY 1, 2
ORDER BY 3 DESC
LIMIT 50
"""

# ── Expensive AI Queries in Query History ─────────────────────────────────────
# Identifies queries that called Cortex/AI functions by scanning query text

AI_QUERIES_FROM_HISTORY = """
SELECT
    query_id,
    query_text,
    user_name,
    warehouse_name,
    ROUND(total_elapsed_time / 1000, 1)     AS elapsed_sec,
    ROUND(credits_used_cloud_services, 6)   AS cloud_svc_credits,
    start_time
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE {date_filter}
  AND execution_status = 'SUCCESS'
  AND (
        UPPER(query_text) LIKE '%SNOWFLAKE.CORTEX.COMPLETE%'
     OR UPPER(query_text) LIKE '%SNOWFLAKE.CORTEX.SUMMARIZE%'
     OR UPPER(query_text) LIKE '%SNOWFLAKE.CORTEX.TRANSLATE%'
     OR UPPER(query_text) LIKE '%SNOWFLAKE.CORTEX.SENTIMENT%'
     OR UPPER(query_text) LIKE '%SNOWFLAKE.CORTEX.EXTRACT_ANSWER%'
     OR UPPER(query_text) LIKE '%SNOWFLAKE.CORTEX.CLASSIFY_TEXT%'
     OR UPPER(query_text) LIKE '%SNOWFLAKE.CORTEX.EMBED_TEXT%'
     OR UPPER(query_text) LIKE '%CORTEX_SEARCH%'
     OR UPPER(query_text) LIKE '%SNOWFLAKE.ML.%'
     OR UPPER(query_text) LIKE '%SNOWFLAKE.DOCUMENT_AI%'
  )
ORDER BY total_elapsed_time DESC
LIMIT 200
"""
