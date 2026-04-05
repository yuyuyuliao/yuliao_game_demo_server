from __future__ import annotations

from typing import Any

from app.command.farm_command import harvest_crop


async def run(land_id: int) -> dict[str, Any]:
    """执行采集作物命令。"""
    return await harvest_crop(land_id)
