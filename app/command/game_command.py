from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.factory import build_agent_registry
from app.command.database import AsyncSessionLocal
from app.model import Player

# 扫雷获胜奖励的金币数量，可以根据实际情况调整。
MINESWEEPER_WIN_GOLD_REWARD = 10
PLAYER_PUBLIC_FIELDS = ("id", "name", "account", "gold", "level")

_AGENT_REGISTRY = build_agent_registry()
minesweeper_assistant = _AGENT_REGISTRY.create("minesweeper")
chess_assistant = _AGENT_REGISTRY.create("chess_suggest")
chess_opponent_assistant = _AGENT_REGISTRY.create("chess_opponent")


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


def _serialize_player(player: Player) -> dict[str, Any]:
    """序列化玩家公开资料，避免暴露敏感字段。"""
    return {field: getattr(player, field) for field in PLAYER_PUBLIC_FIELDS}


async def get_player_info(player_id: str) -> dict[str, Any]:
    """读取指定玩家的公开资料。"""
    async with AsyncSessionLocal() as session:
        player = await _query_player(session, player_id)
        if player is None:
            return {"status": "failed", "reason": f"player not found: {player_id}"}

        return {"status": "success", "player": _serialize_player(player)}


async def add_minesweeper_win_gold(player_id: str) -> dict[str, Any]:
    """给扫雷胜利的指定玩家发放金币奖励。"""
    async with AsyncSessionLocal() as session:
        player = await _query_player(session, player_id)
        if player is None:
            return {"status": "failed", "reason": f"player not found: {player_id}"}

        player.gold += MINESWEEPER_WIN_GOLD_REWARD
        new_gold = player.gold
        await session.commit()

    return {
        "status": "success",
        "player_id": str(player.id),
        "added_gold": MINESWEEPER_WIN_GOLD_REWARD,
        "gold": new_gold,
    }
