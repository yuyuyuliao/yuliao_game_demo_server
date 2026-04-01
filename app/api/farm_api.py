from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.schemas import HarvestRequest, PlantRequest
import app.command.harvest_crop_command as harvest_crop_command
import app.command.list_lands_command as list_lands_command
import app.command.plant_crop_command as plant_crop_command
import app.command.query_crop_status_command as query_crop_status_command

router = APIRouter()


@router.get("/farm/lands")
async def list_lands_api() -> dict[str, list[dict[str, Any]]]:
    """查询全部土地基础信息。"""
    return await list_lands_command.run()


@router.post("/farm/plant")
async def plant_crop_api(payload: PlantRequest) -> dict[str, Any]:
    """在指定土地上种植作物。"""
    return await plant_crop_command.run(payload.land_id, payload.crop_id)


@router.get("/farm/status/{land_id}")
async def query_crop_status_api(land_id: int) -> dict[str, Any]:
    """查询指定土地的作物状态。"""
    return await query_crop_status_command.run(land_id)


@router.post("/farm/harvest")
async def harvest_crop_api(payload: HarvestRequest) -> dict[str, Any]:
    """采集成熟作物。"""
    return await harvest_crop_command.run(payload.land_id)
