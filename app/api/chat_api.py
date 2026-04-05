from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas import ChatRecordRequest, DailyChatRequest
import app.command.daily_chat_command as daily_chat_command
import app.command.record_chat_command as record_chat_command

router = APIRouter()


@router.post("/chat/record")
async def record_chat_api(payload: ChatRecordRequest) -> dict[str, str]:
    """写入玩家聊天记录。"""
    return await record_chat_command.run(payload.player_id, payload.text)


@router.post("/chat/daily")
async def daily_chat_api(payload: DailyChatRequest) -> dict[str, str]:
    """返回玩家日常聊天回复。"""
    return await daily_chat_command.run(payload.player_id, payload.message)
