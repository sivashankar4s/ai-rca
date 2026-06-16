import logging
import time

import boto3

from ...config import get_boto3_kwargs, settings
from ...strategies.data_source import DataSourceStrategy

logger = logging.getLogger(__name__)

# Athena query timeout in seconds
QUERY_TIMEOUT = 120


class AthenaDataSource(DataSourceStrategy):
    def __init__(self):
        self.client = boto3.client("athena", **get_boto3_kwargs())
        logger.info(
            "AthenaDataSource initialised  region=%s  database=%s  table=%s  output=%s",
            settings.aws_region,
            settings.athena_database,
            settings.athena_table,
            settings.athena_output_bucket,
        )

    def fetch_records(
        self,
        time_range: str,
        component: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        failure_only: bool = True,
    ) -> list[dict]:
        # Build the time filter
        if start_date and end_date:
            # Explicit date range from the UI date pickers
            def _fmt(s: str) -> str:
                """Parse a datetime-local string and return Athena TIMESTAMP literal value."""
                from datetime import datetime as _dt
                return _dt.fromisoformat(s).strftime("%Y-%m-%d %H:%M:%S")

            safe_start = _fmt(start_date)
            safe_end   = _fmt(end_date)
            time_filter = (
                f"AND event_inserted_timestamp"
                f" BETWEEN TIMESTAMP '{safe_start}' AND TIMESTAMP '{safe_end}'"
            )
            logger.info(
                "Querying Athena  mode=date_range  start=%s  end=%s  component=%s",
                safe_start, safe_end, component or "<all>",
            )
        else:
            # interval_value / interval_unit are kept separate so Presto/Athena's
            # INTERVAL syntax is satisfied: INTERVAL '1' HOUR  (not INTERVAL '1 HOUR')
            interval_map = {
                "1h": ("1", "HOUR"),
                "1d": ("1", "DAY"),
                "1w": ("7", "DAY"),
            }
            interval_value, interval_unit = interval_map.get(time_range, ("1", "HOUR"))
            time_filter = (
                f"AND CAST(event_inserted_timestamp AS TIMESTAMP)"
                f" >= current_timestamp - INTERVAL '{interval_value}' {interval_unit}"
            )
            logger.info(
                "Querying Athena  mode=relative  time_range=%s  interval=%s %s  component=%s",
                time_range, interval_value, interval_unit, component or "<all>",
            )

        component_filter = ""
        if component:
            # Sanitize component name to prevent SQL injection
            safe_component = component.replace("'", "''")
            component_filter = f"""AND (component_name LIKE '%{safe_component}%'
            OR custom_key2 LIKE '%{safe_component}%' OR custom_key3 LIKE '%{safe_component}%'
            OR custom_key1 LIKE '%{safe_component}%')"""

        status_filter = "AND status = 'FAILED'" if failure_only else ""

        query = f"""
        SELECT
            application_name,
            component_name,
            custom_key1,
            custom_key2,
            custom_key3,
            CAST(event_created_timestamp AS VARCHAR) AS event_created_timestamp,
            CAST(event_inserted_timestamp AS VARCHAR) AS event_inserted_timestamp,
            organization,
            status,
            event_data
        FROM {settings.athena_database}.{settings.athena_table}
        WHERE 1=1
          {status_filter}
          {component_filter}
          {time_filter}
        ORDER BY CAST(event_inserted_timestamp AS TIMESTAMP) DESC
        LIMIT 200
        """

        logger.info("Constructed Athena query:\n%s", query.strip())
        execution_id = self._start_query(query)
        self._wait_for_query(execution_id)
        results = self._get_results(execution_id)
        logger.info("Athena returned %d failure record(s)", len(results))
        return results

    def _start_query(self, query: str) -> str:
        logger.debug("Submitting Athena query:\n%s", query.strip())
        # Only pass ResultConfiguration when an explicit output bucket is configured.
        # If the workgroup manages query results (ManagedQueryResultsConfiguration),
        # passing ResultConfiguration causes an InvalidRequestException.
        params: dict = {
            "QueryString": query,
            "QueryExecutionContext": {"Database": settings.athena_database},
        }
        if settings.athena_output_bucket:
            params["ResultConfiguration"] = {"OutputLocation": settings.athena_output_bucket}
            logger.debug("Using explicit output bucket: %s", settings.athena_output_bucket)
        else:
            logger.debug("No output bucket set — using workgroup-managed query results")
        try:
            response = self.client.start_query_execution(**params)
        except self.client.exceptions.ClientError as exc:
            error_code = exc.response["Error"]["Code"]
            if error_code in ("ExpiredTokenException", "ExpiredToken", "AuthFailure"):
                logger.error(
                    "AWS credentials expired or invalid. "
                    "Update AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN in .env"
                )
                raise RuntimeError(
                    "AWS credentials have expired. "
                    "Please refresh AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and "
                    "AWS_SESSION_TOKEN in your .env file and restart the server."
                ) from exc
            logger.error(
                "Athena StartQueryExecution failed  database=%s  table=%s  error=%s",
                settings.athena_database, settings.athena_table, exc, exc_info=True,
            )
            raise
        except Exception as exc:
            logger.error(
                "Athena StartQueryExecution failed  database=%s  table=%s  output=%s  error=%s",
                settings.athena_database,
                settings.athena_table,
                settings.athena_output_bucket or "(workgroup-managed)",
                exc,
                exc_info=True,
            )
            raise
        execution_id = response["QueryExecutionId"]
        logger.info("Athena query started  execution_id=%s", execution_id)
        return execution_id

    def _wait_for_query(self, execution_id: str):
        logger.debug("Waiting for Athena query  execution_id=%s", execution_id)
        for elapsed in range(QUERY_TIMEOUT):
            response = self.client.get_query_execution(QueryExecutionId=execution_id)
            state = response["QueryExecution"]["Status"]["State"]
            if state == "SUCCEEDED":
                logger.info(
                    "Athena query succeeded  execution_id=%s  elapsed=%ds",
                    execution_id,
                    elapsed,
                )
                return
            if state in ("FAILED", "CANCELLED"):
                reason = response["QueryExecution"]["Status"].get(
                    "StateChangeReason", "Unknown error"
                )
                logger.error(
                    "Athena query %s  execution_id=%s  reason=%s",
                    state,
                    execution_id,
                    reason,
                )
                raise RuntimeError(f"Athena query {state}: {reason}")
            time.sleep(1)
        raise TimeoutError(f"Athena query did not complete within {QUERY_TIMEOUT}s")

    def _get_results(self, execution_id: str) -> list[dict]:
        logger.debug("Fetching Athena results  execution_id=%s", execution_id)
        results = []
        paginator = self.client.get_paginator("get_query_results")
        pages = paginator.paginate(QueryExecutionId=execution_id)

        headers = None
        for page in pages:
            rows = page["ResultSet"]["Rows"]
            for row in rows:
                values = [col.get("VarCharValue", "") for col in row["Data"]]
                if headers is None:
                    headers = values  # first row is column headers
                    continue
                results.append(dict(zip(headers, values)))

        return results
