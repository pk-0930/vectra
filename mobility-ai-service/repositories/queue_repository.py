import json

try:
    from azure.storage.queue import QueueClient
except ImportError:  # pragma: no cover
    QueueClient = None


class AzureQueueRepository:
    def __init__(self, connection_string: str, queue_name: str):
        self.connection_string = connection_string
        self.queue_name = queue_name
        self._client = None

    def _get_client(self):
        if QueueClient is None:
            raise RuntimeError(
                "azure-storage-queue is not installed. "
                "Install backend dependencies before using Azure Queue Storage."
            )

        if self._client is None:
            self._client = QueueClient.from_connection_string(
                conn_str=self.connection_string,
                queue_name=self.queue_name,
            )
        return self._client

    def initialize(self):
        self._get_client().create_queue()

    def send_message(self, payload: dict):
        self._get_client().send_message(json.dumps(payload))
