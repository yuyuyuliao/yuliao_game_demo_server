from __future__ import annotations

import importlib.util
import sqlite3
import subprocess
import sys
from pathlib import Path

from app.command.database import DB_PATH, init_db
from app.model import BaseModel, ChatHistory, Crop, CropInstance, LandPlot, Player, PlayerConversationWindow


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "20260307_seed_farm_data.py"


def test_init_db_runs_migrations_only(tmp_path: Path):
    db_path = tmp_path / "migration-test.db"

    assert ChatHistory.__tablename__ == "chat_history"
    assert LandPlot.__tablename__ == "land_plots"
    assert Crop.__tablename__ == "crops"
    assert CropInstance.__tablename__ == "crop_instances"
    assert Player.__tablename__ == "players"
    assert PlayerConversationWindow.__tablename__ == "player_conversation_windows"
    assert set(BaseModel.metadata.tables) == {"chat_history", "land_plots", "crops", "crop_instances", "players", "player_conversation_windows"}

    init_db(db_path)
    init_db(db_path)

    with sqlite3.connect(db_path) as conn:
        table_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        assert table_names == {"chat_history", "land_plots", "crops", "crop_instances", "players", "player_conversation_windows"}
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 6
        crop_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(crops)").fetchall()
        }
        assert "profit_price" in crop_columns
        crop_instance_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(crop_instances)").fetchall()
        }
        assert crop_instance_columns == {
            "id",
            "index",
            "crop_id",
            "planted_at",
            "last_state_update_at",
            "water",
            "fertility",
            "temperature",
        }
        player_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(players)").fetchall()
        }
        assert player_columns == {"id", "name", "account", "password", "gold", "level"}
        assert conn.execute("SELECT COUNT(*) FROM land_plots").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM crops").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] == 0


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
        assert conn.execute("SELECT COUNT(*) FROM crops").fetchone()[0] == 6

    subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--db-path", str(db_path)],
        check=True,
        cwd=REPO_ROOT,
    )

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM land_plots").fetchone()[0] == 6
        assert conn.execute("SELECT COUNT(*) FROM crops").fetchone()[0] == 6


def test_seed_script_default_db_path_is_game_db():
    spec = importlib.util.spec_from_file_location("seed_farm_data_script", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    args = module.parse_args([])

    assert args.db_path == DB_PATH
    assert args.db_path.name == "game.db"
