from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, text as sql_text
from sqlalchemy.orm import Mapped, mapped_column

from app.model.base import BaseModel


class ChatHistory(BaseModel):
    """玩家聊天历史记录。"""

    __tablename__ = "chat_history"

    # 玩家ID，非空
    player_id: Mapped[str] = mapped_column(String, nullable=False)
    # 聊天文本，非空
    text: Mapped[str] = mapped_column(String, nullable=False)
    # 创建时间，非空，默认为当前时间
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        server_default=sql_text("CURRENT_TIMESTAMP"),
    )
