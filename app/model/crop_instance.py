from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.model.base import BaseModel


class CropInstance(BaseModel):
    """种植中的作物实例。"""

    __tablename__ = "crop_instances"

    # 种植槽位序号，唯一且非空
    index: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
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
