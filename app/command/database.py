from __future__ import annotations

import sqlite3
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "chat.db"
CHROMA_PATH = str(DATA_DIR / "chroma")


def init_db() -> None:
    """初始化聊天和种地系统所需表。"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS land_plots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                price INTEGER NOT NULL,
                description TEXT NOT NULL,
                level INTEGER NOT NULL,
                growth_multiplier REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crops (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                growth_seconds INTEGER NOT NULL,
                price INTEGER NOT NULL,
                description TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crop_instances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                land_id INTEGER NOT NULL UNIQUE,
                crop_id INTEGER NOT NULL,
                planted_at DATETIME NOT NULL,
                last_state_update_at DATETIME NOT NULL,
                water REAL NOT NULL,
                fertility REAL NOT NULL,
                temperature REAL NOT NULL,
                FOREIGN KEY (land_id) REFERENCES land_plots(id),
                FOREIGN KEY (crop_id) REFERENCES crops(id)
            )
            """
        )
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
