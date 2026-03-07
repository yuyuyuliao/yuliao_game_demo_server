from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class Crop:
    id: int
    name: str
    growth_seconds: int
    price: int
    description: str

    @classmethod
    def from_row(cls, row: Any) -> "Crop":
        return cls(
            id=row["id"],
            name=row["name"],
            growth_seconds=row["growth_seconds"],
            price=row["price"],
            description=row["description"],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
