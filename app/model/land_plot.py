from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class LandPlot:
    id: int
    price: int
    description: str
    level: int
    growth_multiplier: float

    @classmethod
    def from_row(cls, row: Any) -> "LandPlot":
        return cls(
            id=row["id"],
            price=row["price"],
            description=row["description"],
            level=row["level"],
            growth_multiplier=row["growth_multiplier"],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
