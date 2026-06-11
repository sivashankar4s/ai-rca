from .config import settings
from .strategies.data_source import DataSourceStrategy
from .strategies.llm import LLMStrategy
from .strategies.log_analysis import LogAnalysisStrategy


def get_data_source() -> DataSourceStrategy:
    if settings.local_data_file:
        from .providers.data_source.local_file import LocalFileDataSource
        return LocalFileDataSource(settings.local_data_file)

    match settings.data_source_provider:
        case "athena":
            from .providers.data_source.athena import AthenaDataSource
            return AthenaDataSource()
        case _:
            raise ValueError(f"Unknown data_source_provider: {settings.data_source_provider}")


def get_llm() -> LLMStrategy:
    match settings.llm_provider:
        case "navify" | "openai":
            from .providers.llm.navify import NavifyLLMProvider
            return NavifyLLMProvider()
        case _:
            raise ValueError(f"Unknown llm_provider: {settings.llm_provider}")


def get_log_backend() -> LogAnalysisStrategy:
    match settings.log_analysis_provider:
        case "cloudwatch":
            from .providers.log_analysis.cloudwatch import CloudWatchLogBackend
            return CloudWatchLogBackend()
        case "grafana_loki":
            from .providers.log_analysis.grafana_loki import GrafanaLokiBackend
            return GrafanaLokiBackend(
                base_url=settings.grafana_loki_url,
                api_key=settings.grafana_api_key,
                datasource_uid=settings.grafana_datasource_uid,
            )
        case _:
            raise ValueError(f"Unknown log_analysis_provider: {settings.log_analysis_provider}")
