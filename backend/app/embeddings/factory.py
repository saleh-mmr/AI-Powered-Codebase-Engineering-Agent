import httpx

from app.core.config import Settings
from app.embeddings.openai import OpenAIEmbeddings
from app.embeddings.provider import EmbeddingProvider


def create_provider(settings: Settings, client: httpx.AsyncClient) -> EmbeddingProvider | None:
    if not settings.embeddings_enabled or settings.openai_api_key is None:
        return None
    return OpenAIEmbeddings(client, settings.openai_api_key.get_secret_value())
