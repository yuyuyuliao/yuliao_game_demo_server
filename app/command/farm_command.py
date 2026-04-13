from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.command.database import AsyncSessionLocal
from app.model import Crop, CropInstance, LandPlot

FARM_DEFAULT_WATER = 100.0
FARM_DEFAULT_FERTILITY = 100.0
FARM_DEFAULT_TEMPERATURE = 22.0
WATER_DECAY_PER_HOUR = 3.0
FERTILITY_DECAY_PER_HOUR = 1.5
LOW_WATER_THRESHOLD = 30.0
LOW_FERTILITY_THRESHOLD = 30.0
MIN_GROWTH_TEMPERATURE = 10.0
MAX_GROWTH_TEMPERATURE = 35.0
LOW_RESOURCE_GROWTH_FACTOR = 0.5
TEMPERATURE_GROWTH_FACTOR = 0.8
TEMPERATURE_CHANGE_PER_HOUR = 0.2
TEMPERATURE_MIN = -10.0
TEMPERATURE_MAX = 45.0
STAGE_HALF_RATIO = 0.5
STAGE_MATURE_RATIO = 1.0
STAGE_WITHER_RATIO = 1.5
MATURE_STAGE = "完全成熟"


def _parse_dt(value: Any) -> datetime:
    """将数据库 DATETIME 值转换为 datetime 对象，支持字符串或 datetime。"""
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"invalid datetime value: {value!r}, expected ISO format string or datetime object"
        ) from exc


async def _apply_land_decay(session: AsyncSession, instance_row: Any) -> Any:
    """根据时间推进土地状态衰减与温度变化。"""
    now = datetime.now()
    last_update = _parse_dt(instance_row["last_state_update_at"])
    elapsed_hours = max(0.0, (now - last_update).total_seconds() / 3600)
    if elapsed_hours <= 0:
        return instance_row

    water = max(0.0, instance_row["water"] - elapsed_hours * WATER_DECAY_PER_HOUR)
    fertility = max(0.0, instance_row["fertility"] - elapsed_hours * FERTILITY_DECAY_PER_HOUR)
    temperature = min(
        TEMPERATURE_MAX,
        max(TEMPERATURE_MIN, instance_row["temperature"] + elapsed_hours * TEMPERATURE_CHANGE_PER_HOUR),
    )

    await session.execute(
        update(CropInstance)
        .where(CropInstance.id == instance_row["id"])
        .values(
            water=water,
            fertility=fertility,
            temperature=temperature,
            last_state_update_at=now,
        )
    )
    await session.commit()
    return await _read_crop_instance(session, instance_row["land_id"])


async def _read_crop_instance(session: AsyncSession, land_id: int) -> Optional[Any]:
    """读取土地上的当前作物实例。"""
    result = await session.execute(
        select(
            CropInstance.id,
            CropInstance.land_id,
            CropInstance.crop_id,
            CropInstance.planted_at,
            CropInstance.last_state_update_at,
            CropInstance.water,
            CropInstance.fertility,
            CropInstance.temperature,
            Crop.name.label("crop_name"),
            Crop.growth_seconds,
            Crop.price.label("crop_price"),
            Crop.description.label("crop_description"),
            LandPlot.level.label("land_level"),
            LandPlot.growth_multiplier.label("growth_multiplier"),
        )
        .join(Crop, Crop.id == CropInstance.crop_id)
        .join(LandPlot, LandPlot.id == CropInstance.land_id)
        .where(CropInstance.land_id == land_id)
    )
    return result.mappings().first()


def _calc_growth_stage(instance_row: Any) -> tuple[str, float]:
    """计算作物当前生长阶段及有效生长秒数。"""
    planted_at = _parse_dt(instance_row["planted_at"])
    elapsed_seconds = max(0.0, (datetime.now() - planted_at).total_seconds())
    growth_speed = instance_row["growth_multiplier"]
    if instance_row["water"] < LOW_WATER_THRESHOLD or instance_row["fertility"] < LOW_FERTILITY_THRESHOLD:
        growth_speed *= LOW_RESOURCE_GROWTH_FACTOR
    if instance_row["temperature"] < MIN_GROWTH_TEMPERATURE or instance_row["temperature"] > MAX_GROWTH_TEMPERATURE:
        growth_speed *= TEMPERATURE_GROWTH_FACTOR
    effective_seconds = elapsed_seconds * growth_speed
    growth_seconds = instance_row["growth_seconds"]
    if effective_seconds < growth_seconds * STAGE_HALF_RATIO:
        return "刚种下", effective_seconds
    if effective_seconds < growth_seconds * STAGE_MATURE_RATIO:
        return "长到一半", effective_seconds
    if effective_seconds < growth_seconds * STAGE_WITHER_RATIO:
        return MATURE_STAGE, effective_seconds
    return "枯萎", effective_seconds


def _build_farming_status(instance_row: Any) -> dict[str, Any]:
    """构建作物状态响应。"""
    stage, effective_seconds = _calc_growth_stage(instance_row)
    return {
        "land_id": instance_row["land_id"],
        "crop_id": instance_row["crop_id"],
        "crop_name": instance_row["crop_name"],
        "crop_description": instance_row["crop_description"],
        "growth_stage": stage,
        "growth_effective_seconds": round(effective_seconds, 2),
        "growth_total_seconds": instance_row["growth_seconds"],
        "land_level": instance_row["land_level"],
        "growth_multiplier": instance_row["growth_multiplier"],
        "water": round(instance_row["water"], 2),
        "fertility": round(instance_row["fertility"], 2),
        "temperature": round(instance_row["temperature"], 2),
        "can_harvest": stage == MATURE_STAGE,
    }


async def list_lands() -> dict[str, list[dict[str, Any]]]:
    """查询全部土地基础信息。"""
    async with AsyncSessionLocal() as session:
        rows = await session.execute(select(LandPlot).order_by(LandPlot.id.asc()))
        lands = [land.to_dict() for land in rows.scalars().all()]
    return {"lands": lands}


async def list_crops() -> dict[str, list[dict[str, Any]]]:
    """查询全部作物基础信息。"""
    async with AsyncSessionLocal() as session:
        rows = await session.execute(select(Crop).order_by(Crop.id.asc()))
        crops = [crop.to_dict() for crop in rows.scalars().all()]
    return {"crops": crops}


async def plant_crop(land_id: int, crop_id: int) -> dict[str, Any]:
    """在指定土地上种植作物。"""
    async with AsyncSessionLocal() as session:
        land = await session.get(LandPlot, land_id)
        if land is None:
            return {"status": "failed", "reason": "land not found"}
        crop = await session.get(Crop, crop_id)
        if crop is None:
            return {"status": "failed", "reason": "crop not found"}
        active = await _read_crop_instance(session, land_id)
        if active is not None:
            return {"status": "failed", "reason": "land already planted"}

        now = datetime.now()
        instance = CropInstance(
            land_id=land_id,
            crop_id=crop_id,
            planted_at=now,
            last_state_update_at=now,
            water=FARM_DEFAULT_WATER,
            fertility=FARM_DEFAULT_FERTILITY,
            temperature=FARM_DEFAULT_TEMPERATURE,
        )
        session.add(instance)
        await session.commit()
        current = await _read_crop_instance(session, land.id)
    return {"status": "planted", "crop_name": crop.name, "land_id": land.id, "state": _build_farming_status(current)}


async def query_crop_status(land_id: int) -> dict[str, Any]:
    """查询指定土地的作物状态。"""
    async with AsyncSessionLocal() as session:
        instance = await _read_crop_instance(session, land_id)
        if instance is None:
            return {"status": "empty", "land_id": land_id}
        refreshed = await _apply_land_decay(session, instance)
    return {"status": "growing", "state": _build_farming_status(refreshed)}


async def harvest_crop(land_id: int) -> dict[str, Any]:
    """采集成熟作物。"""
    async with AsyncSessionLocal() as session:
        instance = await _read_crop_instance(session, land_id)
        if instance is None:
            return {"status": "failed", "reason": "no crop"}
        refreshed = await _apply_land_decay(session, instance)
        stage, _ = _calc_growth_stage(refreshed)
        if stage != MATURE_STAGE:
            return {"status": "failed", "reason": f"crop not ready: {stage}"}
        await session.execute(delete(CropInstance).where(CropInstance.id == refreshed["id"]))
        await session.commit()
        return {
            "status": "harvested",
            "land_id": land_id,
            "crop_name": refreshed["crop_name"],
            "income": refreshed["crop_price"],
        }
