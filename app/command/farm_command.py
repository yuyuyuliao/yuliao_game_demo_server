from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Optional

from app.command.database import DB_PATH
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


def _parse_dt(value: str) -> datetime:
    """将数据库 DATETIME 字符串转换为 datetime。"""
    return datetime.fromisoformat(value)


def _apply_land_decay(conn: sqlite3.Connection, instance_row: sqlite3.Row) -> sqlite3.Row:
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

    conn.execute(
        """
        UPDATE crop_instances
        SET water=?, fertility=?, temperature=?, last_state_update_at=?
        WHERE id=?
        """,
        (water, fertility, temperature, now.isoformat(sep=" "), instance_row["id"]),
    )
    conn.commit()
    return _read_crop_instance(conn, instance_row["land_id"])


def _read_crop_instance(conn: sqlite3.Connection, land_id: int) -> Optional[sqlite3.Row]:
    """读取土地上的当前作物实例。"""
    return conn.execute(
        """
        SELECT ci.id, ci.land_id, ci.crop_id, ci.planted_at, ci.last_state_update_at,
               ci.water, ci.fertility, ci.temperature, c.name AS crop_name, c.growth_seconds,
               c.price AS crop_price, c.description AS crop_description,
               lp.level AS land_level, lp.growth_multiplier AS growth_multiplier
        FROM crop_instances ci
        JOIN crops c ON c.id = ci.crop_id
        JOIN land_plots lp ON lp.id = ci.land_id
        WHERE ci.land_id = ?
        """,
        (land_id,),
    ).fetchone()


def _calc_growth_stage(instance_row: sqlite3.Row) -> tuple[str, float]:
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


def _build_farming_status(instance_row: sqlite3.Row) -> dict[str, Any]:
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


def list_lands() -> dict[str, list[dict[str, Any]]]:
    """查询全部土地基础信息。"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, price, description, level, growth_multiplier
            FROM land_plots
            ORDER BY id ASC
            """
        ).fetchall()
    lands = [LandPlot.from_row(row).to_dict() for row in rows]
    return {"lands": lands}


def plant_crop(land_id: int, crop_id: int) -> dict[str, Any]:
    """在指定土地上种植作物。"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        land_row = conn.execute("SELECT id, price, description, level, growth_multiplier FROM land_plots WHERE id=?", (land_id,)).fetchone()
        if land_row is None:
            return {"status": "failed", "reason": "land not found"}
        land = LandPlot.from_row(land_row)
        crop_row = conn.execute(
            "SELECT id, name, growth_seconds, price, description FROM crops WHERE id=?",
            (crop_id,),
        ).fetchone()
        if crop_row is None:
            return {"status": "failed", "reason": "crop not found"}
        active = _read_crop_instance(conn, land_id)
        if active is not None:
            return {"status": "failed", "reason": "land already planted"}

        crop = Crop.from_row(crop_row)
        now_str = datetime.now().isoformat(sep=" ")
        instance = CropInstance(
            id=None,
            land_id=land.id,
            crop_id=crop_id,
            planted_at=now_str,
            last_state_update_at=now_str,
            water=FARM_DEFAULT_WATER,
            fertility=FARM_DEFAULT_FERTILITY,
            temperature=FARM_DEFAULT_TEMPERATURE,
        )
        conn.execute(
            """
            INSERT INTO crop_instances (
                land_id, crop_id, planted_at, last_state_update_at, water, fertility, temperature
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                instance.land_id,
                instance.crop_id,
                instance.planted_at,
                instance.last_state_update_at,
                instance.water,
                instance.fertility,
                instance.temperature,
            ),
        )
        conn.commit()
        current = _read_crop_instance(conn, land.id)
    return {"status": "planted", "crop_name": crop.name, "land_id": land.id, "state": _build_farming_status(current)}


def query_crop_status(land_id: int) -> dict[str, Any]:
    """查询指定土地的作物状态。"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        instance = _read_crop_instance(conn, land_id)
        if instance is None:
            return {"status": "empty", "land_id": land_id}
        refreshed = _apply_land_decay(conn, instance)
    return {"status": "growing", "state": _build_farming_status(refreshed)}


def harvest_crop(land_id: int) -> dict[str, Any]:
    """采集成熟作物。"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        instance = _read_crop_instance(conn, land_id)
        if instance is None:
            return {"status": "failed", "reason": "no crop"}
        refreshed = _apply_land_decay(conn, instance)
        stage, _ = _calc_growth_stage(refreshed)
        if stage != MATURE_STAGE:
            return {"status": "failed", "reason": f"crop not ready: {stage}"}
        conn.execute("DELETE FROM crop_instances WHERE id=?", (refreshed["id"],))
        conn.commit()
        return {
            "status": "harvested",
            "land_id": land_id,
            "crop_name": refreshed["crop_name"],
            "income": refreshed["crop_price"],
        }
