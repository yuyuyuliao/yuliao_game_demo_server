from __future__ import annotations

from app.command.game_command import suggest_chess


def run(board_fen: str, side_to_move: str | None = None) -> dict[str, str]:
    """执行国际象棋建议命令。"""
    return suggest_chess(board_fen, side_to_move)
