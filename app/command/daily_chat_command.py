from __future__ import annotations

from app.command.chat_command import daily_chat


async def run(player_id: str, message: str) -> dict[str, str]:
    """执行日常聊天命令。"""
    return await daily_chat(player_id, message)
