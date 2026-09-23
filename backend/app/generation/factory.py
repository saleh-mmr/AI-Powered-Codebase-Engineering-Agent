import httpx

from app.core.config import Settings
from app.generation.contracts import AnswerProvider
from app.generation.openai import OpenAIAnswers


def create_answer_provider(settings: Settings, client: httpx.AsyncClient) -> AnswerProvider | None:
    if not settings.answers_enabled:
        return None
    if settings.openai_api_key is None:
        raise ValueError("Enabled answers require a provider key")
    return OpenAIAnswers(
        client,
        settings.openai_api_key.get_secret_value(),
        settings.answer_model,
        settings.answer_max_output_tokens,
    )
