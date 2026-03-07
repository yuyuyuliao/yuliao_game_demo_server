from __future__ import annotations

from typing import Any

from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class BaseModel(DeclarativeBase):
    """SQLAlchemy 模型基类。"""

    __abstract__ = True

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, nullable=False)

    def to_dict(self) -> dict[str, Any]:
        """将 ORM 对象转换为字典。"""
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}
