from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.schemas import HarvestRequest, PlantRequest
from app.command.farm_command import harvest_crop, list_lands, plant_crop, query_crop_status

router = APIRouter()


@router.get("/farm/lands")
async def list_lands_api() -> dict[str, list[dict[str, Any]]]:
    """查询全部土地基础信息。"""
    return await list_lands()


@router.post("/farm/plant")
async def plant_crop_api(payload: PlantRequest) -> dict[str, Any]:
    """在指定土地上种植作物。"""
    return await plant_crop(payload.land_id, payload.crop_id)


@router.get("/farm/status/{land_id}")
async def query_crop_status_api(land_id: int) -> dict[str, Any]:
    """查询指定土地的作物状态。"""
    return await query_crop_status(land_id)


@router.post("/farm/harvest")
async def harvest_crop_api(payload: HarvestRequest) -> dict[str, Any]:
    """采集成熟作物。"""
    return await harvest_crop(payload.land_id)
