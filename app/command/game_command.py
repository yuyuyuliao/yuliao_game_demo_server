from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import ChessOpponentAssistant, ChessSuggestAssistant, MinesweeperAssistant
from app.command.database import AsyncSessionLocal
from app.command.knowledge import knowledge_store
from app.model import Player
from app.prompt import (
    CHESS_OPPONENT_SYSTEM_PROMPT,
    CHESS_SYSTEM_PROMPT,
    MINESWEEPER_SYSTEM_PROMPT,
)

MODEL_NAME = "qwen3:1.7b"
GAME_GOLD_REWARDS = {
    "minesweeper": 10,
    "chess": 20,
}
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


async def _query_player(session: AsyncSession, player_id: str) -> Player | None:
    """按玩家ID、账号或昵称查询玩家记录。

    :param session: 异步数据库会话。
    :param player_id: 玩家标识，支持数字ID、账号或昵称。
    """
    if not player_id:
        return None

    if player_id.isdigit():
        player = await session.get(Player, int(player_id))
        if player is not None:
            return player

    result = await session.execute(
        select(Player).where(or_(Player.account == player_id, Player.name == player_id))
    )
    return result.scalar_one_or_none()


async def add_game_gold(player_id: str, game_id: str) -> dict[str, Any]:
    """根据游戏ID给指定玩家发放金币奖励。"""
    reward_gold = GAME_GOLD_REWARDS.get(game_id)
    if reward_gold is None:
        return {"status": "failed", "reason": f"unknown game_id: {game_id}"}

    async with AsyncSessionLocal() as session:
        player = await _query_player(session, player_id)
        if player is None:
            return {"status": "failed", "reason": f"player not found: {player_id}"}

        player.gold += reward_gold
        new_gold = player.gold
        player_db_id = player.id
        await session.commit()

    return {
        "status": "success",
        "player_id": str(player_db_id),
        "game_id": game_id,
        "added_gold": reward_gold,
        "gold": new_gold,
    }
