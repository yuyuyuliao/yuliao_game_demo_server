from __future__ import annotations

import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import DB_PATH, _init_db, app

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "20260307_seed_farm_data.py"

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def prepare_farm_data() -> None:
    _init_db()
    subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--db-path", str(DB_PATH)],
        check=True,
        cwd=REPO_ROOT,
    )


def _clear_land(index: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('DELETE FROM crop_instances WHERE "index"=?', (index,))
        conn.commit()


def _upsert_player(account: str, name: str, gold: int = 0, level: int = 1) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO players (name, account, password, gold, level)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(account) DO UPDATE SET
                name=excluded.name,
                gold=excluded.gold,
                level=excluded.level
            """,
            (name, account, "hashed-password", gold, level),
        )
        conn.commit()


def _crop_price(crop_id: int) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("SELECT price FROM crops WHERE id=?", (crop_id,)).fetchone()[0]


def test_farm_lands_are_seeded_with_increasing_price():
    response = client.get("/farm/lands")
    assert response.status_code == 200
    lands = response.json()["lands"]
    assert len(lands) >= 2
    ids = [land["id"] for land in lands]
    prices = [land["price"] for land in lands]
    assert ids == sorted(ids)
    assert prices == sorted(prices)


def test_farm_crops_are_seeded_with_basic_info():
    response = client.get("/farm/crops")
    assert response.status_code == 200
    crops = response.json()["plants"]
    assert len(crops) >= 3
    first = crops[0]
    assert set(first) == {"id", "name", "growth_seconds", "price", "description", "profit_price"}
    assert [crop["id"] for crop in crops] == sorted(crop["id"] for crop in crops)
    assert all(crop["growth_seconds"] > 0 for crop in crops)


def test_farm_land_info_returns_current_planted_crop_array():
    index = 3
    crop_id = 1
    player_id = "farm-land-info-player"
    _clear_land(index)
    _upsert_player(player_id, "土地信息玩家", gold=1000)
    client.post("/farm/plant", json={"player_id": player_id, "index": index, "plantId": crop_id})

    response = client.get("/farm/land_info")
    assert response.status_code == 200
    body = response.json()["growingPlants"]
    assert isinstance(body, list)
    matching = [item for item in body if item["Info"]["id"] == crop_id]
    assert matching
    land_info = max(matching, key=lambda item: item["remainGrowthTime"])
    assert set(land_info) == {
        "Info",
        "index",
        "remainGrowthTime",
        "water",
        "fertility",
        "temperature",
    }
    assert set(land_info["Info"]) == {
        "id",
        "name",
        "growth_seconds",
        "price",
        "description",
        "profit_price",
    }
    assert land_info["index"] == index
    assert land_info["Info"]["name"]
    assert land_info["Info"]["growth_seconds"] > 0
    assert land_info["Info"]["price"] > 0
    assert land_info["Info"]["profit_price"] > 0
    assert land_info["remainGrowthTime"] > 0
    assert isinstance(land_info["water"], int)
    assert isinstance(land_info["fertility"], int)
    assert isinstance(land_info["temperature"], int)


def test_farm_plant_query_and_harvest():
    index = 1
    crop_id = 1
    player_id = "farm-plant-harvest-player"
    _clear_land(index)
    _upsert_player(player_id, "种植收获玩家", gold=1000)
    crop_price = _crop_price(crop_id)

    plant = client.post("/farm/plant", json={"player_id": player_id, "index": index, "plantId": crop_id})
    assert plant.status_code == 200
    planted = plant.json()
    assert planted["status"] == "planted"
    assert planted["cost"] == crop_price
    assert planted["gold"] == 1000 - crop_price
    assert planted["state"]["growth_stage"] == "刚种下"

    with sqlite3.connect(DB_PATH) as conn:
        saved_gold = conn.execute(
            "SELECT gold FROM players WHERE account=?",
            (player_id,),
        ).fetchone()[0]
    assert saved_gold == 1000 - crop_price

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE crop_instances
            SET planted_at=?, last_state_update_at=?
            WHERE "index"=?
            """,
            (
                (datetime.now() - timedelta(hours=2)).isoformat(sep=" "),
                (datetime.now() - timedelta(hours=1)).isoformat(sep=" "),
                index,
            ),
        )
        conn.commit()

    status = client.get(f"/farm/status/{index}")
    assert status.status_code == 200
    state = status.json()["state"]
    assert state["growth_stage"] in {"完全成熟", "枯萎"}

    harvest = client.post("/farm/harvest", json={"index": index})
    assert harvest.status_code == 200
    body = harvest.json()
    if state["growth_stage"] == "完全成熟":
        assert body["status"] == "harvested"
        assert body["income"] > 0
    else:
        assert body["status"] == "failed"


def test_farm_state_decay_after_elapsed_time():
    index = 2
    crop_id = 1
    player_id = "farm-state-decay-player"
    _clear_land(index)
    _upsert_player(player_id, "状态衰减玩家", gold=1000)
    client.post("/farm/plant", json={"player_id": player_id, "index": index, "plantId": crop_id})

    first = client.get(f"/farm/status/{index}").json()["state"]
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'UPDATE crop_instances SET last_state_update_at=? WHERE "index"=?',
            ((datetime.now() - timedelta(hours=3)).isoformat(sep=" "), index),
        )
        conn.commit()
    second = client.get(f"/farm/status/{index}").json()["state"]
    assert second["water"] < first["water"]
    assert second["fertility"] < first["fertility"]
    assert second["temperature"] != first["temperature"]


def test_farm_plant_rejects_insufficient_gold_without_planting():
    index = 4
    crop_id = 1
    player_id = "farm-poor-player"
    _clear_land(index)
    _upsert_player(player_id, "金币不足玩家", gold=0)
    crop_price = _crop_price(crop_id)

    response = client.post("/farm/plant", json={"player_id": player_id, "index": index, "plantId": crop_id})

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "status": "failed",
        "reason": "insufficient gold",
        "gold": 0,
        "required_gold": crop_price,
    }
    with sqlite3.connect(DB_PATH) as conn:
        assert conn.execute('SELECT COUNT(*) FROM crop_instances WHERE "index"=?', (index,)).fetchone()[0] == 0
        assert conn.execute("SELECT gold FROM players WHERE account=?", (player_id,)).fetchone()[0] == 0
