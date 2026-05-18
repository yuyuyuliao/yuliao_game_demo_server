from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, text as sql_text
from sqlalchemy.orm import Mapped, mapped_column

from app.model.base import BaseModel


class PlayerConversationWindow(BaseModel):
    """玩家对话窗口 ID 记录。"""

    __tablename__ = "player_conversation_windows"

    player_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        server_default=sql_text("CURRENT_TIMESTAMP"),
    )
