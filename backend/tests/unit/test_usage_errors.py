import asyncio

import httpx
import pytest

from app.core.errors import AppError
from app.core.provider_usage import ProviderUsageError
from app.embeddings.openai import OpenAIEmbeddings
from app.embeddings.provider import MODEL


@pytest.mark.parametrize("valid_usage", [True, False])
def test_invalid_embedding_does_not_erase_valid_usage(valid_usage):
    async def scenario():
        def handle(request):
            return httpx.Response(
                200,
                json={
                    "model": MODEL,
                    "usage": {"prompt_tokens": 2 if valid_usage else 999},
                    "data": [{"index": 0, "embedding": [0.0]}],
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            with pytest.raises(AppError) as caught:
                await OpenAIEmbeddings(client, "unused").embed([[1, 2]])
            if valid_usage:
                assert isinstance(caught.value, ProviderUsageError)
                assert caught.value.input_tokens == 2 and caught.value.output_tokens == 0
            else:
                assert not isinstance(caught.value, ProviderUsageError)

    asyncio.run(scenario())
