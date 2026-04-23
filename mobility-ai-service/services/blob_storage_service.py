import mimetypes
from pathlib import Path

from config.blob_storage_config import get_blob_storage_config
from repositories.blob_storage_repository import BlobStorageRepository


class BlobStorageService:
    def __init__(self, repository: BlobStorageRepository | None = None):
        self.config = get_blob_storage_config()
        self.repository = repository or BlobStorageRepository(self.config.connection_string)

    def upload_video(self, *, blob_name: str, data: bytes, content_type: str | None = None):
        self.repository.upload_bytes(
            container_name=self.config.uploads_container,
            blob_name=blob_name,
            data=data,
            content_type=content_type or "application/octet-stream",
        )

    def download_video_to_file(self, *, blob_name: str, destination_path: str):
        self.repository.download_to_file(
            container_name=self.config.uploads_container,
            blob_name=blob_name,
            destination_path=destination_path,
        )

    def upload_extracted_frames(self, *, source_directory: str, blob_prefix: str) -> list[str]:
        return self.repository.upload_directory(
            container_name=self.config.frames_container,
            source_directory=source_directory,
            blob_prefix=blob_prefix,
        )

    def upload_annotated_frames(self, *, source_directory: str, blob_prefix: str) -> list[str]:
        return self.repository.upload_directory(
            container_name=self.config.annotated_frames_container,
            source_directory=source_directory,
            blob_prefix=blob_prefix,
        )

    def get_annotated_frame(self, blob_name: str) -> tuple[bytes, str]:
        payload = self.repository.download_bytes(
            container_name=self.config.annotated_frames_container,
            blob_name=blob_name,
        )
        content_type, _ = mimetypes.guess_type(Path(blob_name).name)
        return payload, (content_type or "application/octet-stream")
