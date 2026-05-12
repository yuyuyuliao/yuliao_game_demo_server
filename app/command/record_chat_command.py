from __future__ import annotations

from app.command.chat_command import record_chat


async def run(player_id: str, conversation_id: str, role: str, text: str) -> dict[str, str]:
    """执行写入聊天记录命令。"""
    return await record_chat(player_id, conversation_id, role, text)
