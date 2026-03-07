from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.model.base import BaseModel


class CropInstance(BaseModel):
    """土地上的作物实例。"""

    __tablename__ = "crop_instances"

    land_id: Mapped[int] = mapped_column(Integer, ForeignKey("land_plots.id"), nullable=False, unique=True)
    crop_id: Mapped[int] = mapped_column(Integer, ForeignKey("crops.id"), nullable=False)
    planted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_state_update_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    water: Mapped[float] = mapped_column(Float, nullable=False)
    fertility: Mapped[float] = mapped_column(Float, nullable=False)
    temperature: Mapped[float] = mapped_column(Float, nullable=False)
