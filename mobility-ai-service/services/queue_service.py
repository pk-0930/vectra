from config.queue_storage_config import get_queue_storage_config
from repositories.queue_repository import AzureQueueRepository, QueueMessage


class QueueService:
    def __init__(self, repository=None):
        config = get_queue_storage_config()
        self.repository = repository or AzureQueueRepository(
            connection_string=config.connection_string,
            queue_name=config.queue_name,
        )
        try:
            self.repository.initialize()
        except Exception:
            pass

    def enqueue_analysis_job(self, *, job_id: str, analysis_type: str):
        self.repository.send_message(
            {
                "job_id": job_id,
                "analysis_type": analysis_type,
            }
        )

    def receive_analysis_job(self, *, visibility_timeout: int = 1800) -> QueueMessage | None:
        return self.repository.receive_message(visibility_timeout=visibility_timeout)

    def delete_analysis_job(self, message: QueueMessage):
        self.repository.delete_message(message)
