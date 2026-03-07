from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.model.base import BaseModel


class CropInstance(BaseModel):
    """土地上的作物实例。"""

    __tablename__ = "crop_instances"

    # 土地ID，唯一且非空
    land_id: Mapped[int] = mapped_column(Integer, ForeignKey("land_plots.id"), nullable=False, unique=True)
    # 作物ID，非空
    crop_id: Mapped[int] = mapped_column(Integer, ForeignKey("crops.id"), nullable=False)
    # 种植时间，非空
    planted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # 最后一次状态更新的时间，非空
    last_state_update_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # 水分，非空
    water: Mapped[float] = mapped_column(Float, nullable=False)
    # 养分，非空
    fertility: Mapped[float] = mapped_column(Float, nullable=False)
    # 温度，非空
    temperature: Mapped[float] = mapped_column(Float, nullable=False)
