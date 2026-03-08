from __future__ import annotations

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.model.base import BaseModel


class LandPlot(BaseModel):
    """土地基础信息。"""

    __tablename__ = "land_plots"

    # 价格
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    # 名称
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    # 描述
    description: Mapped[str] = mapped_column(String, nullable=False)
    # 级别
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    # 生长速度倍数
    growth_multiplier: Mapped[float] = mapped_column(Float, nullable=False)
