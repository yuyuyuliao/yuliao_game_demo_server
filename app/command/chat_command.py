from __future__ import annotations

import sqlite3

from app.agent import ChatAssistant
from app.command.database import DB_PATH
from app.command.knowledge import knowledge_store
from app.model import ChatHistory
from app.prompt import CHAT_SYSTEM_PROMPT

chat_assistant = ChatAssistant(
    system_prompt=CHAT_SYSTEM_PROMPT,
    model_name="chat-model-v1",
    knowledge_search=knowledge_store.search,
)


def record_chat(player_id: str, text: str) -> dict[str, str]:
    """写入玩家聊天记录到 SQLite。"""
    record = ChatHistory(id=None, player_id=player_id, text=text)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO chat_history (player_id, text) VALUES (?, ?)",
            (record.player_id, record.text),
        )
        conn.commit()
    return {"status": "saved"}


def daily_chat(player_id: str, message: str) -> dict[str, str]:
    """结合历史聊天与知识库返回日常回复。"""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT text FROM chat_history WHERE player_id=? ORDER BY id DESC LIMIT 5",
            (player_id,),
        ).fetchall()

    history = [row[0] for row in rows][::-1]
    return chat_assistant.reply(history, message)
