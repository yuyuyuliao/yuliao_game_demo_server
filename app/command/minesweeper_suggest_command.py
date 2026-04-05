from __future__ import annotations

from typing import Any

from app.command.game_command import suggest_minesweeper


def run(board: str) -> dict[str, Any]:
    """执行扫雷建议命令。"""
    return suggest_minesweeper(board)
