from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas import ChatMessagesRequest, ChatRecordRequest, DailyChatRequest
import app.command.daily_chat_command as daily_chat_command
import app.command.list_chat_messages_command as list_chat_messages_command
import app.command.record_chat_command as record_chat_command

router = APIRouter()


@router.post("/chat/record")
async def record_chat_api(payload: ChatRecordRequest) -> dict[str, str]:
    """写入玩家聊天记录。"""
    return await record_chat_command.run(payload.player_id, payload.conversation_id, payload.role, payload.text)


@router.post("/chat/daily")
async def daily_chat_api(payload: DailyChatRequest) -> dict[str, str]:
    """返回玩家日常聊天回复。"""
    return await daily_chat_command.run(payload.player_id, payload.conversation_id, payload.message)


@router.post("/chat/messages")
async def list_chat_messages_api(payload: ChatMessagesRequest) -> dict[str, object]:
    """按顺序返回对话消息列表。"""
    return await list_chat_messages_command.run(payload.player_id, payload.conversation_id)
