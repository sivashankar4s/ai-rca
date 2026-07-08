"""HealthCheckStrategy ABC — Constitution Principle III (feature 021).

One implementation per AWS service type lives in ``backend/providers/health_check/``.
Each provider wraps its own boto3 client and translates AWS responses into the
uniform ``ServiceHealth`` shape the dashboard renders.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING

from backend.models.schemas import HealthServiceType, ServiceHealthDetail

if TYPE_CHECKING:
    from backend.models.schemas import HealthResource, ServiceHealth


class HealthCheckStrategy(ABC):
    """Abstract interface for a single AWS service-type health checker."""

    service_type: HealthServiceType

    @abstractmethod
    def check(self, ids: list[str], start: datetime, end: datetime) -> "list[ServiceHealth]":
        """Return one ServiceHealth per requested id; window is ``[start, end]``."""

    @abstractmethod
    def discover(self) -> "list[HealthResource]":
        """List resources of this type available in the account (for the config picker)."""

    def detail(
        self, resource_id: str, start: datetime, end: datetime
    ) -> ServiceHealthDetail:
        """Return the run history for one resource over ``[start, end]``.

        Default: no run-level history. Glue jobs/workflows and DataSync tasks override
        this with their native run APIs; Lambda has no run-list API, so its history is
        derived from CloudWatch Logs in the service layer and it keeps this default.
        """
        return ServiceHealthDetail(
            service_type=self.service_type,
            id=resource_id,
            label=resource_id,
            start=start,
            end=end,
        )
