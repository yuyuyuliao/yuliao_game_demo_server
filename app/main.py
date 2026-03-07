from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import chat_router, farm_router, game_router, health_router
from app.command.database import CHROMA_PATH, DB_PATH, init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期：启动时初始化数据库。"""
    init_db()
    yield


app = FastAPI(title="yuliao game demo server", lifespan=lifespan)
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(game_router)
app.include_router(farm_router)


def _init_db() -> None:
    """兼容旧测试与调用方式。"""
    init_db()
