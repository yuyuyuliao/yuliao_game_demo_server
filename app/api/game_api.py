from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.schemas import ChessRequest, MinesweeperRequest, MinesweeperWinRequest, OpponentMoveRequest
import app.command.chess_opponent_move_command as chess_opponent_move_command
import app.command.chess_suggest_command as chess_suggest_command
import app.command.minesweeper_suggest_command as minesweeper_suggest_command
import app.command.minesweeper_win_command as minesweeper_win_command

router = APIRouter()


@router.post("/minesweeper/suggest")
def minesweeper_suggest_api(payload: MinesweeperRequest) -> dict[str, Any]:
    """给出扫雷下一步建议。"""
    return minesweeper_suggest_command.run(payload.board)


@router.post("/chess/suggest")
def chess_suggest_api(payload: ChessRequest) -> dict[str, str]:
    """给出国际象棋建议走法。"""
    return chess_suggest_command.run(payload.board_fen, payload.side_to_move)


@router.post("/chess/opponent-move")
def chess_opponent_move_api(payload: OpponentMoveRequest) -> dict[str, str]:
    """模拟对手在当前局面下的下一步落子。"""
    return chess_opponent_move_command.run(payload.board_fen, payload.player_side)


@router.post("/minesweeper/win")
async def minesweeper_win_api(payload: MinesweeperWinRequest) -> dict[str, Any]:
    """扫雷胜利后给玩家增加金币。"""
    return await minesweeper_win_command.run(payload.player_id)
