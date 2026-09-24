import json
from hashlib import sha256

from app.core.config import Settings
from app.generation.context import PROMPT_HASH
from app.generation.history import HISTORY_POLICY
from app.retrieval.text import VERSION


def config_hash(settings: Settings) -> str:
    # Only public model configuration, never API keys or database credentials.
    configuration = {
        "model": settings.answer_model,
        "generation_transport": "responses-stream-v1",
        "output_cap": settings.answer_max_output_tokens,
        "input_price": settings.answer_input_price_per_million,
        "output_price": settings.answer_output_price_per_million,
        "embedding_price": settings.embedding_price_per_million,
        "prompt": PROMPT_HASH,
        "history_policy": HISTORY_POLICY,
        "retrieval": VERSION,
    }
    return sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest()
