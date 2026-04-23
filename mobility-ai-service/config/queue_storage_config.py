import os
from dataclasses import dataclass


@dataclass(frozen=True)
class QueueStorageConfig:
    connection_string: str
    queue_name: str


def get_queue_storage_config() -> QueueStorageConfig:
    connection_string = (
        os.environ.get("QUEUE_STORAGE_CONNECTION_STRING")
        or os.environ.get("AzureWebJobsStorage")
    )
    if not connection_string:
        raise RuntimeError(
            "Missing queue storage configuration. Set `QUEUE_STORAGE_CONNECTION_STRING` "
            "or `AzureWebJobsStorage`."
        )

    return QueueStorageConfig(
        connection_string=connection_string,
        queue_name=os.environ.get("ANALYSIS_JOBS_QUEUE_NAME", "analysis-jobs"),
    )
