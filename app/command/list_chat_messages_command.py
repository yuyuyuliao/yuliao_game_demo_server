from __future__ import annotations

from app.command.chat_command import list_messages


async def run(player_id: str, conversation_id: str) -> dict[str, object]:
    """执行查询聊天记录命令。"""
    return await list_messages(player_id, conversation_id)
