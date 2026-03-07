from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas import ChatRecordRequest, DailyChatRequest
from app.command.chat_command import daily_chat, record_chat

router = APIRouter()


@router.post("/chat/record")
def record_chat_api(payload: ChatRecordRequest) -> dict[str, str]:
    """写入玩家聊天记录。"""
    return record_chat(payload.player_id, payload.text)


@router.post("/chat/daily")
def daily_chat_api(payload: DailyChatRequest) -> dict[str, str]:
    """返回玩家日常聊天回复。"""
    return daily_chat(payload.player_id, payload.message)
