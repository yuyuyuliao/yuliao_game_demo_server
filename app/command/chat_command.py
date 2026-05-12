from __future__ import annotations

import os

from sqlalchemy import func, select

from app.agent import ChatAssistant
from app.command.database import AsyncSessionLocal
from app.command.knowledge import knowledge_store
from app.command.chat_tools import read_player_farm_info, read_player_info
from app.model import ChatHistory
from app.prompt import CHAT_SYSTEM_PROMPT

PLAYER_HISTORY_PREFIX = "玩家："
ASSISTANT_HISTORY_PREFIX = "助手："

chat_assistant = ChatAssistant(
    system_prompt=CHAT_SYSTEM_PROMPT,
    model_name=os.getenv("OPENAI_CHAT_MODEL", "qwen3:1.7b"),
    knowledge_search=knowledge_store.search,
    player_info_reader=read_player_info,
    farm_info_reader=read_player_farm_info,
)


async def _next_message_order(session, player_id: str, conversation_id: str) -> int:
    value = await session.scalar(
        select(func.max(ChatHistory.message_order)).where(
            ChatHistory.player_id == player_id,
            ChatHistory.conversation_id == conversation_id,
        )
    )
    return (value or 0) + 1


async def record_chat(player_id: str, conversation_id: str, role: str, text: str) -> dict[str, str]:
    """写入聊天记录到 SQLite。"""
    async with AsyncSessionLocal() as session:
        message_order = await _next_message_order(session, player_id, conversation_id)
        session.add(
            ChatHistory(
                player_id=player_id,
                conversation_id=conversation_id,
                role=role,
                text=text,
                message_order=message_order,
            )
        )
        await session.commit()
    return {"status": "saved"}


async def list_messages(player_id: str, conversation_id: str) -> dict[str, object]:
    """按顺序返回单个对话框内的消息。"""
    async with AsyncSessionLocal() as session:
        rows = await session.execute(
            select(ChatHistory)
            .where(
                ChatHistory.player_id == player_id,
                ChatHistory.conversation_id == conversation_id,
            )
            .order_by(ChatHistory.message_order.asc(), ChatHistory.id.asc())
        )
        messages = [
            {
                "id": item.id,
                "player_id": item.player_id,
                "conversation_id": item.conversation_id,
                "role": item.role,
                "text": item.text,
                "message_order": item.message_order,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in rows.scalars().all()
        ]
    return {"conversation_id": conversation_id, "messages": messages}


async def daily_chat(player_id: str, conversation_id: str, message: str) -> dict[str, str]:
    """结合历史聊天与知识库返回日常回复。"""
    async with AsyncSessionLocal() as session:
        rows = await session.execute(
            select(ChatHistory.text)
            .where(
                ChatHistory.player_id == player_id,
                ChatHistory.conversation_id == conversation_id,
            )
            .order_by(ChatHistory.message_order.desc())
            .limit(5)
        )
        history = list(rows.scalars().all())[::-1]
        result = chat_assistant.reply(history, message, player_id=player_id)

        user_order = await _next_message_order(session, player_id, conversation_id)
        ai_order = user_order + 1
        session.add(ChatHistory(player_id=player_id, conversation_id=conversation_id, role="user", text=f"{PLAYER_HISTORY_PREFIX}{message}", message_order=user_order))
        session.add(ChatHistory(player_id=player_id, conversation_id=conversation_id, role="assistant", text=f"{ASSISTANT_HISTORY_PREFIX}{result['response']}", message_order=ai_order))
        await session.commit()
    return result
