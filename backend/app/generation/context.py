import json
from hashlib import sha256
from pathlib import Path

from app.core.errors import AppError
from app.embeddings.tokens import count_tokens
from app.generation.contracts import AnswerDraft
from app.generation.history import HistoryTurn, bounded_history
from app.schemas.search import Evidence

PROMPT_VERSION = "grounded-v2"
INSTRUCTIONS = (Path(__file__).parent / "prompts" / "grounded_v2.txt").read_text(encoding="utf-8")
PROMPT_HASH = sha256(INSTRUCTIONS.encode()).hexdigest()


def build_context(
    question: str, evidence: list[Evidence], history: list[HistoryTurn]
) -> tuple[str, list[HistoryTurn]]:
    selected = bounded_history(history)
    while True:
        # History stays data inside one user payload; no role or system promotion.
        payload = json.dumps(
            {
                "question": question,
                "evidence": [item.model_dump(mode="json") for item in evidence],
                "conversation_history": [turn.model_dump(mode="json") for turn in selected],
            },
            ensure_ascii=False,
        )
        # Preserve the existing total input bound; evidence takes priority over memory.
        if len(payload.encode()) <= 64 * 1024 and count_tokens(INSTRUCTIONS + payload) <= 8000:
            return payload, selected
        if not selected:
            raise AppError(
                "answer_context_limit", "Retrieved context exceeds the answer limit.", 422
            )
        selected.pop(0)


def build_input(question: str, evidence: list[Evidence]) -> str:
    return build_context(question, evidence, [])[0]


def validate_citations(draft: AnswerDraft, evidence: list[Evidence]) -> None:
    known = {item.citation_id for item in evidence}
    if len(known) != len(evidence):
        raise AppError("answer_evidence_invalid", "Source evidence is inconsistent.", 409)
    for claim in draft.claims:
        if len(set(claim.citation_ids)) != len(claim.citation_ids) or not set(
            claim.citation_ids
        ).issubset(known):
            raise AppError(
                "answer_citation_invalid",
                "The answer contained an invalid source reference. No answer was published.",
                502,
            )
