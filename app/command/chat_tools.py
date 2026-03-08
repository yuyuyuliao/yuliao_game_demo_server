from __future__ import annotations

import sqlite3

from app.command.database import DB_PATH


def _connect_db() -> sqlite3.Connection:
    """创建只用于读取聊天辅助信息的 SQLite 连接。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def read_player_info(player_id: str) -> str:
    """读取玩家基础资料，支持按玩家ID、账号或昵称查询。"""
    if not player_id:
        return "未提供玩家标识，暂时无法读取玩家资料。"

    with _connect_db() as conn:
        row = conn.execute(
            """
            SELECT id, name, account, gold, level
            FROM players
            WHERE CAST(id AS TEXT) = ?
               OR account = ?
               OR name = ?
            LIMIT 1
            """,
            (player_id, player_id, player_id),
        ).fetchone()

    if row is None:
        return f"暂未找到玩家 {player_id} 的资料。"

    return (
        f"玩家{row['name']}（ID：{row['id']}，账号：{row['account']}，"
        f"等级：{row['level']}，金币：{row['gold']}）"
    )


def read_player_farm_info(player_id: str) -> str:
    """读取当前玩家可查看的田地概况。"""
    with _connect_db() as conn:
        player_row = None
        if player_id:
            player_row = conn.execute(
                """
                SELECT name
                FROM players
                WHERE CAST(id AS TEXT) = ?
                   OR account = ?
                   OR name = ?
                LIMIT 1
                """,
                (player_id, player_id, player_id),
            ).fetchone()
        rows = conn.execute(
            """
            SELECT lp.id,
                   lp.name,
                   lp.level,
                   lp.growth_multiplier,
                   c.name AS crop_name,
                   ci.water,
                   ci.fertility,
                   ci.temperature
            FROM land_plots AS lp
            LEFT JOIN crop_instances AS ci ON ci.land_id = lp.id
            LEFT JOIN crops AS c ON c.id = ci.crop_id
            ORDER BY lp.id ASC
            """
        ).fetchall()

    if not rows:
        return "当前还没有初始化任何田地数据。"

    owner_name = player_row["name"] if player_row is not None else player_id or "当前玩家"
    planted_rows = [row for row in rows if row["crop_name"]]
    empty_count = len(rows) - len(planted_rows)

    parts = [
        f"{owner_name}当前可查看 {len(rows)} 块田地，"
        f"其中 {len(planted_rows)} 块已种植，{empty_count} 块空闲。"
    ]
    if planted_rows:
        samples = []
        for row in planted_rows[:3]:
            samples.append(
                f"{row['name']}正在种植{row['crop_name']}，"
                f"水分{row['water']:.1f}、肥力{row['fertility']:.1f}、温度{row['temperature']:.1f}℃"
            )
        parts.append("已种植地块：" + "；".join(samples))
    else:
        parts.append("当前所有田地都还没有种下作物。")

    parts.append("演示服暂未区分个人土地归属，以上为该玩家当前可查看的农场概况。")
    return "".join(parts)
