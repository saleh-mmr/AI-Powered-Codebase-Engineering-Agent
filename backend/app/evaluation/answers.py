"""Fixed-context generation evaluation; this deliberately does not benchmark retrieval."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.core.config import Settings
from app.core.errors import AppError
from app.generation.context import (
    INSTRUCTIONS,
    PROMPT_HASH,
    PROMPT_VERSION,
    build_input,
    validate_citations,
)
from app.generation.contracts import AnswerProvider
from app.generation.factory import create_answer_provider
from app.schemas.answer import AnswerRequest
from app.schemas.search import Evidence

DATASET = Path(__file__).resolve().parents[2] / "evaluation" / "answers" / "v1" / "cases.json"


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    question: str
    expected_status: Literal["answered", "insufficient_evidence"]
    expected_facts: list[str]
    forbidden_claims: list[str]
    evidence: list[Evidence] = Field(max_length=8)


def load_cases() -> list[Case]:
    cases = TypeAdapter(list[Case]).validate_json(DATASET.read_bytes())
    if not cases or len({case.id for case in cases}) != len(cases):
        raise ValueError("Dataset IDs must be nonempty and unique")
    for case in cases:
        AnswerRequest(question=case.question)
        build_input(case.question, case.evidence)
        if len({e.citation_id for e in case.evidence}) != len(case.evidence):
            raise ValueError("Duplicate evidence IDs")
        if case.expected_status == "answered" and (not case.evidence or not case.expected_facts):
            raise ValueError("Answerable cases need evidence and expected facts")
    return cases


async def evaluate_case(
    case: Case, provider: AnswerProvider, settings: Settings
) -> dict[str, object]:
    started = perf_counter()
    row: dict[str, object] = {
        "id": case.id,
        "question": case.question,
        "expected_status": case.expected_status,
        "expected_facts": case.expected_facts,
        "forbidden_claims": case.forbidden_claims,
        "evidence": [e.model_dump(mode="json") for e in case.evidence],
        # Human grades must remain null until a reviewer inspects claims against evidence.
        "human_answer_correctness": None,
        "human_groundedness": None,
        "human_citation_support": None,
        "human_notes": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_cost_usd": 0.0,
        "citation_links_valid": None,
        "usage_known": True,
    }
    try:
        if not case.evidence:
            row.update(
                status="insufficient_evidence",
                claims=[],
                model_called=False,
                limitation="No source evidence was retrieved.",
            )
        else:
            row["model_called"] = True
            row["usage_known"] = False
            async with asyncio.timeout(35):
                result = await provider.generate(
                    INSTRUCTIONS, build_input(case.question, case.evidence)
                )
            row.update(
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                usage_known=True,
                model=result.model,
                estimated_cost_usd=(
                    result.input_tokens * settings.answer_input_price_per_million
                    + result.output_tokens * settings.answer_output_price_per_million
                )
                / 1000000,
            )
            if result.refused:
                row.update(status="refused", claims=[])
            else:
                assert result.draft is not None
                row.update(
                    status=result.draft.status,
                    claims=[c.model_dump() for c in result.draft.claims],
                    limitation=result.draft.limitation,
                )
                row["citation_links_valid"] = False
                validate_citations(result.draft, case.evidence)
                row["citation_links_valid"] = True if result.draft.claims else None
        row["expected_status_match"] = row["status"] == case.expected_status
    except (AppError, TimeoutError) as exc:
        row.update(
            status="error",
            expected_status_match=False,
            error_code=exc.code if isinstance(exc, AppError) else "evaluation_timeout",
        )
    row["duration_ms"] = round((perf_counter() - started) * 1000, 2)
    return row


async def run_evaluation(settings: Settings) -> dict[str, object]:
    cases = load_cases()
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as client:
        provider = create_answer_provider(settings, client)
        if provider is None:
            raise ValueError("Enable APP_ANSWERS_ENABLED for a paid evaluation")
        rows = [await evaluate_case(case, provider, settings) for case in cases]
    return {
        "dataset": "answers-v1-fixed-context",
        "dataset_sha256": sha256(DATASET.read_bytes()).hexdigest(),
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": PROMPT_HASH,
        "model": settings.answer_model,
        "max_output_tokens": settings.answer_max_output_tokens,
        "input_price_per_million": settings.answer_input_price_per_million,
        "output_price_per_million": settings.answer_output_price_per_million,
        "created_at": datetime.now(UTC).isoformat(),
        "cases": rows,
        "expected_status_accuracy": sum(row["expected_status_match"] is True for row in rows)
        / len(rows),
        "errors": sum(row["status"] == "error" for row in rows),
        "note": "Status accuracy is not factual accuracy. Human grades are intentionally unfilled. "
        "Failed calls with unknown usage may still be billed. No retrieval is evaluated here.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check", action="store_true", help="Validate fixture only; no network or key"
    )
    mode.add_argument(
        "--allow-paid", action="store_true", help="Send synthetic evidence to the real provider"
    )
    parser.add_argument("--output", type=Path, default=Path("evaluation/answers/reports/run.json"))
    args = parser.parse_args()
    if args.check:
        print(
            json.dumps(
                {
                    "valid_cases": len(load_cases()),
                    "provider_calls": 0,
                    "dataset_sha256": sha256(DATASET.read_bytes()).hexdigest(),
                }
            )
        )
        return
    # Shared Settings validates provider configuration. This runner never connects to a database.
    settings = Settings(
        database_url="postgresql+asyncpg://evaluation:unused@localhost/evaluation_test"
    )
    result = asyncio.run(run_evaluation(settings))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Wrote {args.output}; review per-case answers and fill human grades.")


if __name__ == "__main__":
    main()
