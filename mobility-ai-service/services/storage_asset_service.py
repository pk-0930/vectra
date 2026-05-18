import os
from datetime import date
import mimetypes
from pathlib import Path

from repositories.blob_storage_repository import BlobStorageRepository
from services.blob_storage_service import BlobStorageService


class StorageAssetService:
    def __init__(self, repository: BlobStorageRepository | None = None):
        self.blob_storage_service = BlobStorageService(repository=repository)
        self.repository = self.blob_storage_service.repository

    def upload_progress_photo(self, *, client_id: int, filename: str, data: bytes, content_type: str | None):
        blob_name = f"client-{client_id}/{filename}"
        self.repository.upload_bytes(
            container_name="client-progress-photos",
            blob_name=blob_name,
            data=data,
            content_type=content_type or "application/octet-stream",
        )
        return blob_name

    def upload_plan_pdf(self, *, plan_kind: str, plan_id: int, data: bytes):
        container_name = "nutrition-plan-pdfs" if plan_kind == "nutrition" else "workout-plan-pdfs"
        blob_name = f"{plan_kind}-plan-{plan_id}.pdf"
        self.repository.upload_bytes(
            container_name=container_name,
            blob_name=blob_name,
            data=data,
            content_type="application/pdf",
        )
        return blob_name

    def build_progress_photo_path(self, blob_name: str) -> str:
        return blob_name

    def get_progress_photo(self, blob_name: str) -> tuple[bytes, str]:
        payload = self.repository.download_bytes(
            container_name="client-progress-photos",
            blob_name=blob_name,
        )
        content_type, _ = mimetypes.guess_type(Path(blob_name).name)
        return payload, (content_type or "application/octet-stream")
