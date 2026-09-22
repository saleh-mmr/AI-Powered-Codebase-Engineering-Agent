from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Ranked:
    chunk_id: UUID
    score: float
    channel_ranks: dict[str, int]


def fuse(
    channels: dict[str, list[UUID]], limit: int = 8, tie_keys: dict[UUID, str] | None = None
) -> list[Ranked]:
    scores: dict[UUID, float] = {}
    ranks: dict[UUID, dict[str, int]] = {}
    for channel, ids in channels.items():
        for position, chunk_id in enumerate(dict.fromkeys(ids), 1):
            scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (60 + position)
            ranks.setdefault(chunk_id, {})[channel] = position
    ordered = sorted(scores, key=lambda key: (-scores[key], (tie_keys or {}).get(key, str(key))))[
        :limit
    ]
    return [Ranked(key, scores[key], ranks[key]) for key in ordered]
