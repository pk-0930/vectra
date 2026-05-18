from config.queue_storage_config import get_queue_storage_config
from repositories.queue_repository import AzureQueueRepository, QueueMessage


class QueueService:
    def __init__(self, repository=None, poison_repository=None):
        config = get_queue_storage_config()
        self.config = config
        self.repository = repository or AzureQueueRepository(
            connection_string=config.connection_string,
            queue_name=config.queue_name,
        )
        self.poison_repository = poison_repository or AzureQueueRepository(
            connection_string=config.connection_string,
            queue_name=config.poison_queue_name,
        )
        try:
            self.repository.initialize()
        except Exception:
            pass
        try:
            self.poison_repository.initialize()
        except Exception:
            pass

    def enqueue_analysis_job(self, *, job_id: str, analysis_type: str):
        self.repository.send_message(
            {
                "job_id": job_id,
                "analysis_id": job_id,
                "analysis_type": analysis_type,
            }
        )

    def receive_analysis_job(self, *, visibility_timeout: int = 1800) -> QueueMessage | None:
        return self.repository.receive_message(visibility_timeout=visibility_timeout)

    def delete_analysis_job(self, message: QueueMessage):
        self.repository.delete_message(message)

    def enqueue_poison_job(self, payload: dict):
        self.poison_repository.send_message(payload)
