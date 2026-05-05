from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ChatRecordRequest(BaseModel):
    """聊天记录写入请求体。"""

    player_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class DailyChatRequest(BaseModel):
    """日常聊天请求体，包含玩家 ID 和当前消息。"""

    player_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


class MinesweeperRequest(BaseModel):
    """扫雷建议请求体，board 为二维棋盘。"""

    board: str


class ChessRequest(BaseModel):
    """国际象棋建议请求体。"""

    board_fen: str
    side_to_move: Optional[str] = "white"


class OpponentMoveRequest(BaseModel):
    """国际象棋对手落子请求体。"""

    board_fen: str
    player_side: str


class MinesweeperWinRequest(BaseModel):
    """扫雷胜利奖励请求体。"""

    player_id: str = Field(min_length=1)


class PlantRequest(BaseModel):
    """种植请求体。"""

    player_id: str = Field(min_length=1)
    index: int
    plantId: int = Field(gt=0)


class HarvestRequest(BaseModel):
    """采集请求体。"""

    index: int = Field(gt=0)
