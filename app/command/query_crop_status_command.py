from __future__ import annotations

from typing import Any

from app.command.farm_command import query_crop_status


async def run(index: int) -> dict[str, Any]:
    """执行查询作物状态命令。"""
    return await query_crop_status(index)
