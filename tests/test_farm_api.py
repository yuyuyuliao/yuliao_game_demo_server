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


def _clear_land(land_id: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM crop_instances WHERE land_id=?", (land_id,))
        conn.commit()


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
    crops = response.json()["crops"]
    assert len(crops) >= 3
    first = crops[0]
    assert set(first) == {"id", "name", "growth_seconds", "price", "description", "profit_price"}
    assert [crop["id"] for crop in crops] == sorted(crop["id"] for crop in crops)
    assert all(crop["growth_seconds"] > 0 for crop in crops)


def test_farm_plant_query_and_harvest():
    land_id = 1
    crop_id = 1
    _clear_land(land_id)

    plant = client.post("/farm/plant", json={"land_id": land_id, "crop_id": crop_id})
    assert plant.status_code == 200
    planted = plant.json()
    assert planted["status"] == "planted"
    assert planted["state"]["growth_stage"] == "刚种下"

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE crop_instances
            SET planted_at=?, last_state_update_at=?
            WHERE land_id=?
            """,
            (
                (datetime.now() - timedelta(hours=2)).isoformat(sep=" "),
                (datetime.now() - timedelta(hours=1)).isoformat(sep=" "),
                land_id,
            ),
        )
        conn.commit()

    status = client.get(f"/farm/status/{land_id}")
    assert status.status_code == 200
    state = status.json()["state"]
    assert state["growth_stage"] in {"完全成熟", "枯萎"}

    harvest = client.post("/farm/harvest", json={"land_id": land_id})
    assert harvest.status_code == 200
    body = harvest.json()
    if state["growth_stage"] == "完全成熟":
        assert body["status"] == "harvested"
        assert body["income"] > 0
    else:
        assert body["status"] == "failed"


def test_farm_state_decay_after_elapsed_time():
    land_id = 2
    crop_id = 1
    _clear_land(land_id)
    client.post("/farm/plant", json={"land_id": land_id, "crop_id": crop_id})

    first = client.get(f"/farm/status/{land_id}").json()["state"]
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE crop_instances SET last_state_update_at=? WHERE land_id=?",
            ((datetime.now() - timedelta(hours=3)).isoformat(sep=" "), land_id),
        )
        conn.commit()
    second = client.get(f"/farm/status/{land_id}").json()["state"]
    assert second["water"] < first["water"]
    assert second["fertility"] < first["fertility"]
    assert second["temperature"] != first["temperature"]
