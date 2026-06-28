import os
from dataclasses import dataclass


PLACEHOLDER_VALUES = {
    "",
    "replace-with-azure-openai-endpoint",
    "replace-with-azure-openai-api-key",
    "replace-with-azure-openai-deployment",
}


@dataclass(frozen=True)
class AzureOpenAIConfig:
    endpoint: str
    api_key: str
    deployment: str
    api_version: str

    @property
    def chat_completions_url(self) -> str:
        endpoint = self.endpoint.rstrip("/")
        return (
            f"{endpoint}/openai/deployments/{self.deployment}/chat/completions"
            f"?api-version={self.api_version}"
        )


def get_azure_openai_config() -> AzureOpenAIConfig | None:
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

    if any(value in PLACEHOLDER_VALUES for value in (endpoint, api_key, deployment)):
        return None

    return AzureOpenAIConfig(
        endpoint=endpoint,
        api_key=api_key,
        deployment=deployment,
        api_version=api_version,
    )
