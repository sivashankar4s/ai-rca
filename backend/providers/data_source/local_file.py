import json
import logging

from ...strategies.data_source import DataSourceStrategy

logger = logging.getLogger(__name__)


class LocalFileDataSource(DataSourceStrategy):
    """Loads failure records from a local JSON file (development only)."""

    def __init__(self, path: str):
        self._path = path
        logger.info("LocalFileDataSource initialised  file=%s", path)

    def fetch_records(
        self,
        time_range: str,
        component: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        failure_only: bool = True,
    ) -> list[dict]:
        logger.info("Loading local failure data  file=%s", self._path)
        try:
            with open(self._path, encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError as exc:
            raise RuntimeError(f"LOCAL_DATA_FILE not found: {self._path}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"LOCAL_DATA_FILE is not valid JSON: {exc}") from exc

        records: list[dict] = data if isinstance(data, list) else data.get("records", [])

        if component:
            records = [r for r in records if r.get("component_name") == component]

        logger.info(
            "Loaded %d record(s) from local file (component=%s)",
            len(records),
            component or "<all>",
        )
        return records
