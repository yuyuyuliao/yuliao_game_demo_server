from __future__ import annotations

from sqlalchemy import Integer, String, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.model.base import BaseModel


class Crop(BaseModel):
    """作物基础配置。"""

    __tablename__ = "crops"

    # 作物名称，唯一且非空
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    # 生长时间，单位为秒，非空
    growth_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    # 价格，非空
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    # 描述，非空
    description: Mapped[str] = mapped_column(String, nullable=False)
    # 获利，非空
    profit_price: Mapped[int] = mapped_column(Integer, nullable=False)
