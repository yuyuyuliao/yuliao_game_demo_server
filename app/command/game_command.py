from __future__ import annotations

from typing import Any, Optional

from app.agent import ChessOpponentAssistant, ChessSuggestAssistant, MinesweeperAssistant
from app.command.knowledge import knowledge_store
from app.prompt import (
    CHESS_OPPONENT_SYSTEM_PROMPT,
    CHESS_SYSTEM_PROMPT,
    MINESWEEPER_SYSTEM_PROMPT,
)

MODEL_NAME = "qwen3:1.7b"
minesweeper_assistant = MinesweeperAssistant(
    system_prompt=MINESWEEPER_SYSTEM_PROMPT,
    model_name=MODEL_NAME,
)
chess_assistant = ChessSuggestAssistant(
    system_prompt=CHESS_SYSTEM_PROMPT,
    model_name=MODEL_NAME,
    knowledge_search=knowledge_store.search,
)
chess_opponent_assistant = ChessOpponentAssistant(
    system_prompt=CHESS_OPPONENT_SYSTEM_PROMPT,
    model_name=MODEL_NAME,
)


def suggest_minesweeper(board: str) -> dict[str, Any]:
    """给出扫雷下一步建议。"""
    return minesweeper_assistant.suggest(board)


def suggest_chess(board_fen: str, side_to_move: Optional[str] = None) -> dict[str, str]:
    """给出国际象棋建议走法。"""
    return chess_assistant.suggest(board_fen, side_to_move)


def suggest_chess_opponent_move(board_fen: str, player_side: str) -> dict[str, str]:
    """模拟对手在当前局面下的下一步落子。"""
    return chess_opponent_assistant.suggest(board_fen, player_side)
