import asyncio

from app.core.config import Settings
from app.evaluation.answers import evaluate_case, load_cases
from app.generation.contracts import AnswerDraft, Claim, GenerationResult


class Provider:
    model = "test"
    calls = 0

    async def generate(self, instructions, evidence_input):
        self.calls += 1
        return GenerationResult(
            model="test",
            refused=False,
            input_tokens=100,
            output_tokens=20,
            draft=AnswerDraft(
                status="answered",
                claims=[Claim(text="A fake claim", citation_ids=["C999"])],
                limitation="",
            ),
        )


def test_fixture_includes_negative_and_injection_cases():
    cases = load_cases()
    assert len(cases) == 8
    assert {c.id for c in cases} >= {"missing-context", "irrelevant-context", "comment-injection"}


def test_evaluation_preserves_invalid_citation_failure_and_usage():
    settings = Settings(database_url="postgresql+asyncpg://a:b@localhost/test")
    provider = Provider()
    result = asyncio.run(evaluate_case(load_cases()[0], provider, settings))
    assert result["status"] == "error" and result["citation_links_valid"] is False
    assert result["input_tokens"] == 100
    assert result["human_groundedness"] is None
    assert result["expected_status_match"] is False
    empty = next(case for case in load_cases() if not case.evidence)
    result = asyncio.run(evaluate_case(empty, provider, settings))
    assert result["expected_status_match"] is True and result["model_called"] is False
    assert provider.calls == 1


def test_followup_fixture_includes_wrong_history_injection_and_missing_evidence():
    from app.evaluation.answers import DATASET

    cases = load_cases(DATASET.parents[1] / "followups-v1" / "cases.json")
    assert len(cases) == 4 and all(case.history for case in cases)
    assert {case.id for case in cases} >= {
        "false-prior-answer",
        "history-injection",
        "history-without-evidence",
    }
