from __future__ import annotations

from sqlalchemy import select

from app.agent.factory import build_agent_registry
from app.command.database import AsyncSessionLocal
from app.model import ChatHistory
PLAYER_HISTORY_PREFIX = "玩家："
ASSISTANT_HISTORY_PREFIX = "助手："

_AGENT_REGISTRY = build_agent_registry()
chat_assistant = _AGENT_REGISTRY.create("chat")


async def record_chat(player_id: str, text: str) -> dict[str, str]:
    """写入玩家聊天记录到 SQLite。"""
    async with AsyncSessionLocal() as session:
        session.add(ChatHistory(player_id=player_id, text=text))
        await session.commit()
    return {"status": "saved"}


async def daily_chat(player_id: str, message: str) -> dict[str, str]:
    """结合历史聊天与知识库返回日常回复。"""
    async with AsyncSessionLocal() as session:
        rows = await session.execute(
            select(ChatHistory.text)
            .where(ChatHistory.player_id == player_id)
            .order_by(ChatHistory.id.desc())
            .limit(5)
        )
        history = list(rows.scalars().all())[::-1]
        result = chat_assistant.reply(history, message, player_id=player_id)
        session.add(ChatHistory(player_id=player_id, text=f"{PLAYER_HISTORY_PREFIX}{message}"))
        session.add(ChatHistory(player_id=player_id, text=f"{ASSISTANT_HISTORY_PREFIX}{result['response']}"))
        await session.commit()
    return result
