from __future__ import annotations

from typing import Any

from app.command.farm_command import list_land_info


async def run() -> dict[str,list[dict[str, Any]]]:
    return await list_land_info()
