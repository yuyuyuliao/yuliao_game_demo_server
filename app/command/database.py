from __future__ import annotations

import sqlite3
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "chat.db"
CHROMA_PATH = str(DATA_DIR / "chroma")
MIGRATIONS_DIR = APP_DIR / "migrations"


def _migration_files() -> list[Path]:
    """按版本顺序返回迁移文件。"""
    return sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))


def run_migrations(db_path: Path = DB_PATH) -> None:
    """执行尚未应用的 SQLite 迁移脚本。"""
    migration_files = _migration_files()
    with sqlite3.connect(db_path) as conn:
        current_version = conn.execute("PRAGMA user_version").fetchone()[0]
        for migration_file in migration_files:
            version = int(migration_file.name.split("_", 1)[0])
            if version <= current_version:
                continue
            conn.executescript(migration_file.read_text(encoding="utf-8"))
            conn.execute(f"PRAGMA user_version = {version}")
        conn.commit()


def _seed_initial_data(db_path: Path) -> None:
    """初始化基础种地配置数据。"""
    with sqlite3.connect(db_path) as conn:
        land_count = conn.execute("SELECT COUNT(*) FROM land_plots").fetchone()[0]
        if land_count == 0:
            conn.executemany(
                """
                INSERT INTO land_plots (price, description, level, growth_multiplier)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (100, "1号地：靠近小溪，土壤松软。", 1, 1.00),
                    (180, "2号地：有石板路，适合新手。", 1, 1.00),
                    (300, "3号地：老农留下的试验田。", 2, 1.10),
                    (480, "4号地：向阳高地，温度更稳定。", 2, 1.10),
                    (720, "5号地：微风谷地，生长速度更快。", 3, 1.20),
                    (1020, "6号地：传说中的金色土壤。", 4, 1.30),
                ],
            )
        crop_count = conn.execute("SELECT COUNT(*) FROM crops").fetchone()[0]
        if crop_count == 0:
            conn.executemany(
                """
                INSERT INTO crops (name, growth_seconds, price, description)
                VALUES (?, ?, ?, ?)
                """,
                [
                    ("胡萝卜", 3600, 30, "成长稳定，适合练手。"),
                    ("玉米", 7200, 60, "成熟后收益更高。"),
                    ("草莓", 5400, 80, "甜度高但对水量要求更高。"),
                ],
            )
        conn.commit()


def init_db(db_path: Path = DB_PATH) -> None:
    """通过迁移初始化数据库，并补齐基础种子数据。"""
    run_migrations(db_path)
    _seed_initial_data(db_path)
