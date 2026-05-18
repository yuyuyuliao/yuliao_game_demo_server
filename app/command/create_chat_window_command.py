from __future__ import annotations

import uuid

from sqlalchemy import text as sql_text

from app.command.database import AsyncSessionLocal


async def run(player_id: str) -> dict[str, str]:
    """创建并返回唯一对话窗口 ID。"""
    conversation_id = uuid.uuid4().hex

    async with AsyncSessionLocal() as session:
        await session.execute(
            sql_text(
                """
                INSERT INTO player_conversation_windows (player_id, conversation_id)
                VALUES (:player_id, :conversation_id)
                """
            ),
            {"player_id": player_id, "conversation_id": conversation_id},
        )
        await session.commit()

    return {"player_id": player_id, "conversation_id": conversation_id}
