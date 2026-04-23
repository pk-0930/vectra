import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BlobStorageConfig:
    connection_string: str
    uploads_container: str
    frames_container: str
    annotated_frames_container: str


def get_blob_storage_config() -> BlobStorageConfig:
    connection_string = (
        os.environ.get("BLOB_STORAGE_CONNECTION_STRING")
        or os.environ.get("AzureWebJobsStorage")
    )
    if not connection_string:
        raise RuntimeError(
            "Missing blob storage configuration. Set `BLOB_STORAGE_CONNECTION_STRING` "
            "or `AzureWebJobsStorage`."
        )

    return BlobStorageConfig(
        connection_string=connection_string,
        uploads_container=os.environ.get("BLOB_UPLOADS_CONTAINER", "uploads"),
        frames_container=os.environ.get("BLOB_FRAMES_CONTAINER", "frames"),
        annotated_frames_container=os.environ.get(
            "BLOB_ANNOTATED_FRAMES_CONTAINER",
            "annotated-frames",
        ),
    )
