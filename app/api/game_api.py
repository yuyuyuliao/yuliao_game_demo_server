from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.schemas import AddGameGoldRequest, ChessRequest, MinesweeperRequest, OpponentMoveRequest
from app.command.game_command import add_game_gold, suggest_chess, suggest_chess_opponent_move, suggest_minesweeper

router = APIRouter()


@router.post("/minesweeper/suggest")
def minesweeper_suggest_api(payload: MinesweeperRequest) -> dict[str, Any]:
    """给出扫雷下一步建议。"""
    return suggest_minesweeper(payload.board)


@router.post("/chess/suggest")
def chess_suggest_api(payload: ChessRequest) -> dict[str, str]:
    """给出国际象棋建议走法。"""
    return suggest_chess(payload.board_fen, payload.side_to_move)


@router.post("/chess/opponent-move")
def chess_opponent_move_api(payload: OpponentMoveRequest) -> dict[str, str]:
    """模拟对手在当前局面下的下一步落子。"""
    return suggest_chess_opponent_move(payload.board_fen, payload.player_side)


@router.post("/game/add-gold")
async def add_game_gold_api(payload: AddGameGoldRequest) -> dict[str, Any]:
    """根据游戏ID给玩家增加金币。"""
    return await add_game_gold(payload.player_id, payload.game_id)
