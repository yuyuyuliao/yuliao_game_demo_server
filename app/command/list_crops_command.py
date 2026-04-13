from __future__ import annotations

from typing import Any

from app.command.farm_command import list_crops


async def run() -> dict[str, list[dict[str, Any]]]:
    """执行查询作物列表命令。"""
    return await list_crops()
