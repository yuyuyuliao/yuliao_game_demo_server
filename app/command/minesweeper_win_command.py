from __future__ import annotations

from typing import Any

from app.command.game_command import add_minesweeper_win_gold


async def run(player_id: str) -> dict[str, Any]:
    """执行扫雷胜利奖励命令。"""
    return await add_minesweeper_win_gold(player_id)
