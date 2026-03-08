from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.model.base import BaseModel


class Player(BaseModel):
    """玩家基础信息。"""

    __tablename__ = "players"

    # 名称
    name: Mapped[str] = mapped_column(String, nullable=False)
    # 账号，唯一且非空
    account: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    # 密码，非空
    password: Mapped[str] = mapped_column(String, nullable=False)
    # 金币，非空，默认 0
    gold: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 等级，非空，默认 1
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
