from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, text as sql_text
from sqlalchemy.orm import Mapped, mapped_column

from app.model.base import BaseModel


class ChatHistory(BaseModel):
    """玩家聊天历史记录。"""

    __tablename__ = "chat_history"

    player_id: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        server_default=sql_text("CURRENT_TIMESTAMP"),
    )
