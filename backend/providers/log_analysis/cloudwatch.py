import logging
import time
from datetime import UTC, datetime, timedelta

import boto3

from ...config import get_boto3_kwargs, settings
from ...strategies.log_analysis import LogAnalysisStrategy

logger = logging.getLogger(__name__)

QUERY_TIMEOUT = 60


class CloudWatchLogBackend(LogAnalysisStrategy):
    def __init__(self):
        self.client = boto3.client("logs", **get_boto3_kwargs())
        logger.debug(
            "CloudWatchLogBackend initialised  region=%s  log_group=%s",
            settings.aws_region,
            settings.cloudwatch_log_group,
        )

    def execute_query(
        self,
        query: str,
        time_range: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[str]:
        if start_date and end_date:
            start_time = int(datetime.fromisoformat(start_date).timestamp())
            end_time = int(datetime.fromisoformat(end_date).timestamp())
        else:
            range_seconds = {"1h": 3600, "1d": 86400, "1w": 604800}
            end_time = int(time.time())
            start_time = end_time - range_seconds.get(time_range, 3600)

        logger.info(
            "Starting CloudWatch Insights query  log_group=%s  time_range=%s",
            settings.cloudwatch_log_group,
            time_range,
        )
        logger.debug("CloudWatch query string: %s", query)

        try:
            response = self.client.start_query(
                logGroupName=settings.cloudwatch_log_group,
                startTime=start_time,
                endTime=end_time,
                queryString=query,
                limit=50,
            )
            query_id = response["queryId"]
            logger.info("CloudWatch query started  query_id=%s", query_id)
            return self._wait_and_fetch(query_id)
        except self.client.exceptions.ResourceNotFoundException:
            logger.warning(
                "CloudWatch log group not found: %s", settings.cloudwatch_log_group
            )
            return [f"[Log group '{settings.cloudwatch_log_group}' not found]"]
        except Exception as e:
            logger.error("CloudWatch query error: %s", e, exc_info=True)
            return [f"[CloudWatch query error: {e}]"]

    def _wait_and_fetch(self, query_id: str) -> list[str]:
        for elapsed in range(QUERY_TIMEOUT):
            response = self.client.get_query_results(queryId=query_id)
            status = response["status"]

            if status == "Complete":
                logs = []
                for result in response["results"]:
                    line = " | ".join(
                        f"{f['field']}={f['value']}"
                        for f in result
                        if f["field"] not in ("@ptr",)
                    )
                    logs.append(line)
                logger.info(
                    "CloudWatch query complete  query_id=%s  elapsed=%ds  lines=%d",
                    query_id,
                    elapsed,
                    len(logs),
                )
                return logs

            if status in ("Failed", "Cancelled", "Timeout"):
                logger.warning(
                    "CloudWatch query ended early  query_id=%s  status=%s",
                    query_id,
                    status,
                )
                return [f"[CloudWatch query ended with status: {status}]"]

            time.sleep(1)

        logger.warning("CloudWatch query timed out  query_id=%s", query_id)
        return ["[CloudWatch query timed out]"]

    def build_deep_link(
        self,
        region: str,
        log_group: str,
        component: str,
        time_range: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> str:
        """Build a CloudWatch Logs Insights console deep-link for the given component."""
        if start_date and end_date:
            start_dt = datetime.fromisoformat(start_date).replace(tzinfo=UTC)
            end_dt = datetime.fromisoformat(end_date).replace(tzinfo=UTC)
        else:
            deltas = {"1h": timedelta(hours=1), "1d": timedelta(days=1), "1w": timedelta(weeks=1)}
            delta = deltas.get(time_range, timedelta(hours=1))
            end_dt = datetime.now(UTC)
            start_dt = end_dt - delta
        end_iso = end_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        # AWS CloudWatch console uses tilde-encoding (* as escape char)
        def tilde_enc(s: str) -> str:
            char_map = {
                " ": "*20", "/": "*2F", ":": "*3A", "@": "*40",
                "|": "*7C", "(": "*28", ")": "*29", "[": "*5B",
                "]": "*5D", ",": "*2C", "=": "*3D", "'": "*27",
                '"': "*22", "$": "*24", "*": "*2A", "?": "*3F",
                "&": "*26", "#": "*23", "+": "*2B", "%": "*25",
            }
            return "".join(char_map.get(c, c) for c in s)

        query = (
            f"fields @timestamp, @message"
            f" | filter @message like /{component}/"
            f" | sort @timestamp desc"
            f" | limit 50"
        )

        lg_enc = tilde_enc(log_group)
        q_enc = tilde_enc(query)
        start_enc = tilde_enc(start_iso)
        end_enc = tilde_enc(end_iso)

        fragment = (
            f"logsV2:logs-insights$3FqueryDetail$3D"
            f"~(end~'{end_enc}'"
            f"~logGroupNames~!(~'{lg_enc}')"
            f"~queryString~'{q_enc}'"
            f"~start~'{start_enc}')"
        )
        return (
            f"https://{region}.console.aws.amazon.com/cloudwatch/home"
            f"?region={region}#{fragment}"
        )
