from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class ChatHistory:
    id: int | None
    player_id: str
    text: str
    created_at: str | None = None

    @classmethod
    def from_row(cls, row: Any) -> "ChatHistory":
        return cls(
            id=row["id"],
            player_id=row["player_id"],
            text=row["text"],
            created_at=row["created_at"],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
