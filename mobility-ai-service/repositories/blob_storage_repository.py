import mimetypes
import os
from pathlib import Path

try:
    from azure.storage.blob import BlobServiceClient, ContentSettings
except ImportError:  # pragma: no cover - exercised only when dependency is missing
    BlobServiceClient = None
    ContentSettings = None


class BlobStorageRepository:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self._client = None

    def _get_client(self):
        if BlobServiceClient is None:
            raise RuntimeError(
                "azure-storage-blob is not installed. "
                "Install backend dependencies before running blob-backed storage."
            )

        if self._client is None:
            self._client = BlobServiceClient.from_connection_string(self.connection_string)

        return self._client

    def ensure_container(self, container_name: str):
        container_client = self._get_client().get_container_client(container_name)
        try:
            container_client.create_container()
        except Exception:
            pass

    def upload_bytes(
        self,
        *,
        container_name: str,
        blob_name: str,
        data: bytes,
        content_type: str | None = None,
    ):
        self.ensure_container(container_name)
        blob_client = self._get_client().get_blob_client(container=container_name, blob=blob_name)

        kwargs = {}
        if content_type and ContentSettings is not None:
            kwargs["content_settings"] = ContentSettings(content_type=content_type)

        blob_client.upload_blob(data, overwrite=True, **kwargs)

    def upload_file(
        self,
        *,
        container_name: str,
        blob_name: str,
        file_path: str,
        content_type: str | None = None,
    ):
        if content_type is None:
            guessed_type, _ = mimetypes.guess_type(file_path)
            content_type = guessed_type

        with open(file_path, "rb") as handle:
            self.upload_bytes(
                container_name=container_name,
                blob_name=blob_name,
                data=handle.read(),
                content_type=content_type,
            )

    def upload_directory(
        self,
        *,
        container_name: str,
        source_directory: str,
        blob_prefix: str,
    ) -> list[str]:
        uploaded_blob_names: list[str] = []
        root_path = Path(source_directory)

        for file_path in sorted(root_path.rglob("*")):
            if not file_path.is_file():
                continue

            relative_path = file_path.relative_to(root_path).as_posix()
            normalized_prefix = blob_prefix.rstrip("/")
            blob_name = (
                f"{normalized_prefix}/{relative_path}"
                if normalized_prefix
                else relative_path
            )
            self.upload_file(
                container_name=container_name,
                blob_name=blob_name,
                file_path=str(file_path),
            )
            uploaded_blob_names.append(blob_name)

        return uploaded_blob_names

    def download_bytes(self, *, container_name: str, blob_name: str) -> bytes:
        blob_client = self._get_client().get_blob_client(container=container_name, blob=blob_name)
        return blob_client.download_blob().readall()

    def download_to_file(self, *, container_name: str, blob_name: str, destination_path: str):
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        payload = self.download_bytes(container_name=container_name, blob_name=blob_name)
        with open(destination_path, "wb") as handle:
            handle.write(payload)
