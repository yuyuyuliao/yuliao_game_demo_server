from __future__ import annotations

import sqlite3
from pathlib import Path

from app.command.database import init_db
from app.model import BaseModel, ChatHistory, Crop, CropInstance, LandPlot


def test_init_db_runs_sql_migrations_and_seeds_once(tmp_path: Path):
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
        assert conn.execute("SELECT COUNT(*) FROM land_plots").fetchone()[0] == 6
        assert conn.execute("SELECT COUNT(*) FROM crops").fetchone()[0] == 3
