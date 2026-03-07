from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

from app.command.database import init_db
from app.model import BaseModel, ChatHistory, Crop, CropInstance, LandPlot


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "20260307_seed_farm_data.py"


def test_init_db_runs_migrations_only(tmp_path: Path):
    db_path = tmp_path / "migration-test.db"

    assert ChatHistory.__tablename__ == "chat_history"
    assert LandPlot.__tablename__ == "land_plots"
    assert Crop.__tablename__ == "crops"
    assert CropInstance.__tablename__ == "crop_instances"
    assert set(BaseModel.metadata.tables) == {"chat_history", "land_plots", "crops", "crop_instances"}

    init_db(db_path)
    init_db(db_path)

    with sqlite3.connect(db_path) as conn:
        table_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        assert table_names == {"chat_history", "land_plots", "crops", "crop_instances"}
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM land_plots").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM crops").fetchone()[0] == 0


def test_seed_script_inserts_default_farm_data_once(tmp_path: Path):
    db_path = tmp_path / "seed-script.db"

    init_db(db_path)
    subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--db-path", str(db_path)],
        check=True,
        cwd=REPO_ROOT,
    )

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM land_plots").fetchone()[0] == 6
        assert conn.execute("SELECT COUNT(*) FROM crops").fetchone()[0] == 3

    subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--db-path", str(db_path)],
        check=True,
        cwd=REPO_ROOT,
    )

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM land_plots").fetchone()[0] == 6
        assert conn.execute("SELECT COUNT(*) FROM crops").fetchone()[0] == 3
