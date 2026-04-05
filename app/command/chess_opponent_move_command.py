from __future__ import annotations

from app.command.game_command import suggest_chess_opponent_move


def run(board_fen: str, player_side: str) -> dict[str, str]:
    """执行国际象棋对手落子命令。"""
    return suggest_chess_opponent_move(board_fen, player_side)
