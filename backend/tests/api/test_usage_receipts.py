import asyncio
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select, update
from test_answer_runs import queue, worker
from test_conversations import setup
from test_repositories import sign_in

from app.core.errors import AppError
from app.core.provider_usage import ProviderUsageError
from app.models import AnswerRun, UsageReceipt


@pytest.mark.parametrize("outcome", ["success", "citation", "provider", "invalid", "cancel"])
def test_receipts_survive_failure_and_cancellation(auth_client, outcome):
    headers, _, url, provider = setup(auth_client)
    run = queue(auth_client, headers, url).json()
    path = "/answer-runs/" + run["id"]
    assert auth_client.get(path + "/usage").json() == {
        "tracked": True,
        "items": [],
        "known_cost_usd": "0",
        "unknown_calls": 0,
    }
    generate = provider.generate

    async def call(instructions, payload):
        async with auth_client.app.state.test_factory() as db:
            receipt = await db.scalar(select(UsageReceipt))
            assert receipt is not None and receipt.input_tokens is None  # committed before call
            if outcome == "cancel":
                await db.execute(update(AnswerRun).values(status="cancelled", lease_token=None))
                await db.commit()
        if outcome == "invalid":
            raise ProviderUsageError(AppError("model_invalid", "Invalid output", 502), 100, 40)
        return await generate(instructions, payload)

    provider.generate = call
    provider.fail = outcome == "provider"
    if outcome == "citation":
        provider.citation = "C999"
    worker(auth_client, provider, run["id"])
    worker(auth_client, provider, run["id"])
    result = auth_client.get(path + "/usage").json()
    assert len(result["items"]) == 1
    receipt = result["items"][0]
    if outcome == "provider":
        assert result["unknown_calls"] == 1 and receipt["estimated_cost_usd"] is None
    else:
        assert result["unknown_calls"] == 0
        assert receipt["input_tokens"] == 100 and receipt["output_tokens"] == 40
        assert Decimal(result["known_cost_usd"]) == Decimal("0.000104")
        assert receipt["finished_at"] is not None
    if outcome != "success":
        assert auth_client.get(url + "/messages").json()["items"] == []
    assert "question" not in receipt and "payload" not in receipt
    sign_in(auth_client, "receipt-outsider@example.com")
    assert auth_client.get(path + "/usage").status_code == 404


def test_legacy_and_cancelled_before_start_have_no_invented_receipts(auth_client):
    headers, _, url, provider = setup(auth_client)
    run = queue(auth_client, headers, url).json()
    path = "/answer-runs/" + run["id"]
    auth_client.post(path + "/cancel", json={}, headers=headers)
    worker(auth_client, provider, run["id"])
    assert auth_client.get(path + "/usage").json()["items"] == []

    async def legacy():
        async with auth_client.app.state.test_factory() as db:
            await db.execute(
                update(AnswerRun).where(AnswerRun.id == UUID(run["id"])).values(receipt_version=0)
            )
            await db.commit()

    asyncio.run(legacy())
    assert auth_client.get(path + "/usage").json()["tracked"] is False


def test_query_receipt_rates_and_deletion(auth_client):
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from sqlalchemy import delete

    from app.services.usage_receipts import ReceiptWriter

    headers, _, url, _ = setup(auth_client)
    run = queue(auth_client, headers, url).json()

    async def scenario():
        factory = auth_client.app.state.test_factory
        token = uuid4()
        async with factory() as db:
            await db.execute(
                update(AnswerRun).values(
                    status="running",
                    lease_token=token,
                    lease_expires_at=datetime.now(UTC) + timedelta(seconds=60),
                )
            )
            await db.commit()
        writer = ReceiptWriter(factory, UUID(run["id"]), token)
        receipt_id = await writer.begin("query_embedding", "fixture", 0.02)
        await writer.finish(receipt_id, 50, 0)
        await writer.finish(receipt_id, 999, 0)  # first receipt is immutable
        async with factory() as db:
            receipt = await db.get(UsageReceipt, receipt_id)
            assert receipt.input_tokens == 50
            assert receipt.estimated_cost_usd == Decimal("0.000001")
            await db.execute(delete(AnswerRun).where(AnswerRun.id == UUID(run["id"])))
            await db.commit()
        await writer.finish(receipt_id, 50, 0)  # deletion is never undone
        async with factory() as db:
            assert await db.get(UsageReceipt, receipt_id) is None

    asyncio.run(scenario())
