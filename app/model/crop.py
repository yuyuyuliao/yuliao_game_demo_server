from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.model.base import BaseModel


class Crop(BaseModel):
    """作物基础配置。"""

    __tablename__ = "crops"

    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    growth_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
