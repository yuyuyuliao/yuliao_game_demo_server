from __future__ import annotations

from datetime import datetime
from math import ceil
from typing import Any, Optional

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.command.database import AsyncSessionLocal
from app.model import Crop, CropInstance, LandPlot, Player

DEFAULT_LAND_LEVEL = 1
DEFAULT_GROWTH_MULTIPLIER = 1.0

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


async def _get_land_by_index(session: AsyncSession, index: int) -> Optional[LandPlot]:
    rows = await session.execute(select(LandPlot).order_by(LandPlot.id.asc()))
    lands = list(rows.scalars().all())
    if index <= 0 or index > len(lands):
        return None
    return lands[index - 1]


async def _query_player(session: AsyncSession, player_id: str) -> Optional[Player]:
    if not player_id:
        return None

    if player_id.isdigit():
        player = await session.get(Player, int(player_id))
        if player is not None:
            return player

    result = await session.execute(
        select(Player).where(or_(Player.account == player_id, Player.name == player_id))
    )
    return result.scalar_one_or_none()


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
    return await _read_crop_instance(session, instance_row["index"])


async def _read_crop_instance(session: AsyncSession, index: int) -> Optional[Any]:
    """读取指定序号土地上的当前作物实例。"""
    result = await session.execute(
        select(
            CropInstance.id,
            CropInstance.index,
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
            Crop.profit_price,
        )
        .join(Crop, Crop.id == CropInstance.crop_id)
        .where(CropInstance.index == index)
    )
    row = result.mappings().first()
    if row is None:
        return None

    land = await _get_land_by_index(session, index)
    return {
        **row,
        "land_id": land.id if land is not None else None,
        "land_level": land.level if land is not None else DEFAULT_LAND_LEVEL,
        "growth_multiplier": land.growth_multiplier if land is not None else DEFAULT_GROWTH_MULTIPLIER,
    }


async def _read_crop_instances(session: AsyncSession) -> list[Any]:
    result = await session.execute(
        select(
            CropInstance.id,
            CropInstance.index,
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
            Crop.profit_price,
        )
        .join(Crop, Crop.id == CropInstance.crop_id)
        .order_by(CropInstance.index.asc())
    )
    rows = list(result.mappings().all())

    lands_result = await session.execute(select(LandPlot).order_by(LandPlot.id.asc()))
    lands = list(lands_result.scalars().all())

    instances: list[dict[str, Any]] = []
    for row in rows:
        land = lands[row["index"] - 1] if 0 < row["index"] <= len(lands) else None
        instances.append(
            {
                **row,
                "land_id": land.id if land is not None else None,
                "land_level": land.level if land is not None else DEFAULT_LAND_LEVEL,
                "growth_multiplier": land.growth_multiplier if land is not None else DEFAULT_GROWTH_MULTIPLIER,
            }
        )
    return instances


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
        "index": instance_row["index"],
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


def _calc_remain_growth_time(instance_row: Any) -> int:
    _, effective_seconds = _calc_growth_stage(instance_row)
    return ceil(max(0.0, instance_row["growth_seconds"] - effective_seconds))


def _build_land_info(instance_row: Any) -> dict[str, Any]:
    return {
        "Info": {
            "id": instance_row["crop_id"],
            "name": instance_row["crop_name"],
            "growth_seconds": instance_row["growth_seconds"],
            "price": instance_row["crop_price"],
            "description": instance_row["crop_description"],
            "profit_price": instance_row["profit_price"],
        },
        "index": instance_row["index"],
        "remainGrowthTime": _calc_remain_growth_time(instance_row),
        "water": round(instance_row["water"]),
        "fertility": round(instance_row["fertility"]),
        "temperature": round(instance_row["temperature"]),
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
    return {"plants": crops}


async def list_land_info() ->  dict[str,list[dict[str, Any]]]:
    async with AsyncSessionLocal() as session:
        instances = await _read_crop_instances(session)
        refreshed = [await _apply_land_decay(session, instance) for instance in instances]
    return {"growingPlants": [_build_land_info(instance) for instance in refreshed]}


async def plant_crop(player_id: str, index: int, crop_id: int) -> dict[str, Any]:
    """在指定序号的土地上种植作物。"""
    async with AsyncSessionLocal() as session:
        player = await _query_player(session, player_id)
        if player is None:
            return {"status": "failed", "reason": f"player not found: {player_id}"}

        crop = await session.get(Crop, crop_id)
        if crop is None:
            return {"status": "failed", "reason": "crop not found"}
        active_result = await session.execute(
            select(CropInstance.id).where(CropInstance.index == index)
        )
        active = active_result.scalar_one_or_none()
        if active is not None:
            return {"status": "failed", "reason": "land already planted"}

        if player.gold < crop.price:
            return {
                "status": "failed",
                "reason": "insufficient gold",
                "gold": player.gold,
                "required_gold": crop.price,
            }

        now = datetime.now()
        instance = CropInstance(
            index=index,
            crop_id=crop_id,
            planted_at=now,
            last_state_update_at=now,
            water=FARM_DEFAULT_WATER,
            fertility=FARM_DEFAULT_FERTILITY,
            temperature=FARM_DEFAULT_TEMPERATURE,
        )
        session.add(instance)
        player.gold -= crop.price
        current_gold = player.gold
        await session.flush()
        current = await _read_crop_instance(session, index)
        if current is None:
            return {"status": "failed", "reason": "crop state not found"}
        await session.commit()
    return {
        "status": "planted",
        "crop_name": crop.name,
        "index": index,
        "gold": current_gold,
        "cost": crop.price,
        "state": _build_farming_status(current),
    }


async def query_crop_status(index: int) -> dict[str, Any]:
    """查询指定序号土地的作物状态。"""
    async with AsyncSessionLocal() as session:
        land = await _get_land_by_index(session, index)
        if land is None:
            return {"status": "failed", "reason": "land index not found"}
        instance = await _read_crop_instance(session, index)
        if instance is None:
            return {"status": "empty", "index": index}
        refreshed = await _apply_land_decay(session, instance)
    return {"status": "growing", "state": _build_farming_status(refreshed)}


async def harvest_crop(index: int) -> dict[str, Any]:
    """采集指定序号土地上的成熟作物。"""
    async with AsyncSessionLocal() as session:
        land = await _get_land_by_index(session, index)
        if land is None:
            return {"status": "failed", "reason": "land index not found"}
        instance = await _read_crop_instance(session, index)
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
            "index": index,
            "crop_name": refreshed["crop_name"],
            "income": refreshed["crop_price"],
        }
