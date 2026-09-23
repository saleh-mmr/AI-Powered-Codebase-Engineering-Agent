import json
from hashlib import sha256
from pathlib import Path

from app.core.errors import AppError
from app.embeddings.tokens import count_tokens
from app.generation.contracts import AnswerDraft
from app.schemas.search import Evidence

PROMPT_VERSION = "grounded-v1"
INSTRUCTIONS = (Path(__file__).parent / "prompts" / "grounded_v1.txt").read_text(encoding="utf-8")
PROMPT_HASH = sha256(INSTRUCTIONS.encode()).hexdigest()


def build_input(question: str, evidence: list[Evidence]) -> str:
    # JSON keeps data separate from instructions; it is not a prompt-injection boundary alone.
    payload = json.dumps(
        {"question": question, "evidence": [item.model_dump(mode="json") for item in evidence]},
        ensure_ascii=False,
    )
    # cl100k is an operational size estimate, not this model's exact billing tokenizer.
    if len(payload.encode()) > 64 * 1024 or count_tokens(INSTRUCTIONS + payload) > 8000:
        raise AppError("answer_context_limit", "Retrieved context exceeds the answer limit.", 422)
    return payload


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
