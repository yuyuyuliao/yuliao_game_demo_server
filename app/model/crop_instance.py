from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class CropInstance:
    id: int | None
    land_id: int
    crop_id: int
    planted_at: str
    last_state_update_at: str
    water: float
    fertility: float
    temperature: float

    @classmethod
    def from_row(cls, row: Any) -> "CropInstance":
        return cls(
            id=row["id"],
            land_id=row["land_id"],
            crop_id=row["crop_id"],
            planted_at=row["planted_at"],
            last_state_update_at=row["last_state_update_at"],
            water=row["water"],
            fertility=row["fertility"],
            temperature=row["temperature"],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
