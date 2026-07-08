"""LambdaHealthCheck — health of AWS Lambda functions via boto3 (feature 021).

Current status is the function's ``State``; the failure count is the number of failed
invocations found in the function's own CloudWatch log group (``/aws/lambda/<name>``)
over the lookback window — the same log detector the drill-down uses. The ``Errors``
metric is intentionally not used: it misses handler-caught ``[ERROR]`` failures that
still show up as failed invocations in the console.
"""

import logging
from datetime import datetime

from botocore.exceptions import BotoCoreError, ClientError

from backend.models.schemas import (
    HealthResource,
    HealthServiceType,
    HealthStatus,
    ServiceHealth,
)
from backend.providers.data_source.cloudwatch import CloudWatchDataSource
from backend.providers.health_check._aws import build_client
from backend.strategies.health_check import HealthCheckStrategy

logger = logging.getLogger(__name__)


class LambdaHealthCheck(HealthCheckStrategy):
    service_type = HealthServiceType.LAMBDA_FUNCTION

    def __init__(self, aws_credentials: dict | None = None) -> None:
        self._lambda = build_client("lambda", aws_credentials)
        self._credentials = aws_credentials

    def discover(self) -> list[HealthResource]:
        names: list[str] = []
        params: dict = {}
        try:
            while True:
                resp = self._lambda.list_functions(**params)
                names.extend(fn["FunctionName"] for fn in resp.get("Functions", []))
                marker = resp.get("NextMarker")
                if not marker:
                    break
                params["Marker"] = marker
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"Lambda discovery failed: {exc}") from exc
        return [HealthResource(id=n, label=n) for n in names]

    def check(self, ids: list[str], start: datetime, end: datetime) -> list[ServiceHealth]:
        return [self._check_one(name, start, end) for name in ids]

    def _check_one(self, name: str, start: datetime, end: datetime) -> ServiceHealth:
        try:
            cfg = self._lambda.get_function_configuration(FunctionName=name)
        except (BotoCoreError, ClientError) as exc:
            return ServiceHealth(
                service_type=self.service_type,
                id=name,
                label=name,
                status=HealthStatus.UNKNOWN,
                detail=f"Lambda check failed: {exc}",
            )
        state = cfg.get("State", "")
        status = HealthStatus.UP if state == "Active" else HealthStatus.DOWN
        return ServiceHealth(
            service_type=self.service_type,
            id=name,
            label=name,
            status=status,
            failure_count=self._failed_invocation_count(name, start, end),
            detail=f"State={state}",
        )

    def _failed_invocation_count(self, name: str, start: datetime, end: datetime) -> int:
        """Count failed invocations from the function's own CloudWatch log group."""
        source = CloudWatchDataSource(
            log_groups=[f"/aws/lambda/{name}"], aws_credentials=self._credentials
        )
        try:
            return len(source.fetch_records(start, end))
        except RuntimeError as exc:
            # No log group yet (never invoked) or a transient query failure — treat as
            # zero failures for the card; the drill-down surfaces real query errors.
            logger.warning("Lambda %s failure-count query failed: %s", name, exc)
            return 0
