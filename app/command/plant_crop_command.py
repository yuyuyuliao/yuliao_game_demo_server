from __future__ import annotations

from typing import Any

from app.command.farm_command import plant_crop


async def run(index: int, crop_id: int) -> dict[str, Any]:
    """执行种植作物命令。"""
    return await plant_crop(index, crop_id)
