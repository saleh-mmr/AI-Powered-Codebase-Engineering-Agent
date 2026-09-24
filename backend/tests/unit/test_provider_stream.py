import asyncio
import json

import httpx
import pytest
from test_generation import MODEL, draft, payload

from app.core.errors import AppError
from app.generation.openai import OpenAIAnswers
from app.generation.preview import preview_text


class Chunks(httpx.AsyncByteStream):
    def __init__(self, body):
        self.body = body

    async def __aiter__(self):
        for i in range(0, len(self.body), 7):
            yield self.body[i : i + 7]


def events(final=None):
    text = draft().model_dump_json()
    complete = final or payload()
    complete["output"][0]["id"] = "msg1"
    return [
        {"type": "response.created", "sequence_number": 0},
        {
            "type": "response.output_text.delta",
            "sequence_number": 1,
            "item_id": "msg1",
            "output_index": 0,
            "content_index": 0,
            "delta": text[:45],
        },
        {
            "type": "response.output_text.delta",
            "sequence_number": 2,
            "item_id": "msg1",
            "output_index": 0,
            "content_index": 0,
            "delta": text[45:],
        },
        {"type": "response.completed", "sequence_number": 3, "response": complete},
    ]


def run(items, content_type="text/event-stream"):
    received, calls = [], []

    async def exercise():
        async def delta(text):
            received.append(text)

        def handle(request):
            calls.append(request)
            body = json.loads(request.content)
            assert body["stream"] is True and body["store"] is False and body["tools"] == []
            assert body["model"] == MODEL and body["text"]["format"]["strict"] is True
            wire = "".join(
                "event: " + event["type"] + "\r\ndata: " + json.dumps(event) + "\r\n\r\n"
                for event in items
            ).encode()
            return httpx.Response(200, headers={"content-type": content_type}, stream=Chunks(wire))

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            result = await OpenAIAnswers(client, "private-key", MODEL, 1200).generate_stream(
                "instructions", "{}", delta
            )
            return result

    try:
        return asyncio.run(exercise()), received
    finally:
        assert len(calls) == 1


def test_real_stream_contract_fragments_and_completed_envelope():
    result, received = run(events())
    assert result.draft == draft() and result.input_tokens == 100
    assert len(received) == 2 and "".join(received) == draft().model_dump_json()


@pytest.mark.parametrize(
    "failure",
    [
        "eof",
        "duplicate",
        "item",
        "mismatch",
        "usage",
        "incomplete",
        "malformed",
        "oversized",
        "content-type",
    ],
)
def test_stream_failures_never_retry_or_accept_partial_output(failure):
    items = events()
    content_type = "text/event-stream"
    if failure == "eof":
        items.pop()
    elif failure == "duplicate":
        items[2]["sequence_number"] = 1
    elif failure == "item":
        items[2]["item_id"] = "different"
    elif failure == "mismatch":
        items[1]["delta"] = "changed"
    elif failure == "usage":
        items[-1]["response"]["usage"]["total_tokens"] = 0
    elif failure == "incomplete":
        items[-1]["type"] = "response.incomplete"
    elif failure == "malformed":
        items[1]["delta"] = 123
    elif failure == "oversized":
        items[1]["delta"] = "x" * 66000
    else:
        content_type = "application/json"
    with pytest.raises(AppError) as error:
        run(items, content_type)
    assert error.value.code in {"model_invalid", "model_incomplete"}
    assert "private-key" not in str(error.value)


def test_refusal_and_reasoning_events_are_not_forwarded():
    final = payload([{"type": "refusal", "text": "private refusal detail"}])
    items = [
        {
            "type": "response.reasoning_text.delta",
            "sequence_number": 0,
            "delta": "private reasoning",
        },
        {"type": "response.refusal.delta", "sequence_number": 1, "delta": "refusal"},
        {"type": "response.completed", "sequence_number": 2, "response": final},
    ]
    result, received = run(items)
    assert result.refused and received == []


def test_partial_projection_is_text_only_bounded_and_not_final_validation():
    assert preview_text('{"claims":[{"text":"Hello') == "Hello"
    assert preview_text('{"reasoning":"hidden", "citation_ids":["C1"]}') == ""
    assert preview_text('{"claims":[{"text":"<script>alert(1)</script>"}]}').startswith("<script>")
    assert preview_text('{"claims":[{"text":123}]}') == ""
    assert preview_text("not json") == ""
    assert len(preview_text(json.dumps({"claims": [{"text": "a" * 1800}] * 8}))) == 8000
    assert "\x00" not in preview_text('{"claims":[{"text":"a\\u0000b"}]}')
