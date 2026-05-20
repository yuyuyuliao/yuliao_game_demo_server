from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine, or_
from sqlalchemy.orm import Session, sessionmaker

from app.command.database import DB_PATH
from app.model import Crop, CropInstance, Player

SYNC_ENGINE = create_engine(
    f"sqlite:///{DB_PATH}",
    future=True,
    connect_args={"check_same_thread": False},
)
SyncSessionLocal = sessionmaker(bind=SYNC_ENGINE, class_=Session)


def _query_player(session: Session, player_id: str) -> Player | None:
    """按玩家 ID、账号或名称查询玩家记录。"""
    if not player_id:
        return None
    player = None
    if player_id.isdigit():
        player = session.query(Player).filter(Player.id == int(player_id)).first()
    if player is not None:
        return player
    return session.query(Player).filter(or_(Player.account == player_id, Player.name == player_id)).first()


def read_player_info(player_id: str) -> str:
    """读取玩家基础资料，支持按玩家 ID、账号或名称查询。"""
    print(f"[chat_tool] read_player_info start player_id={player_id!r}")
    if not player_id:
        result = "未提供玩家标识，暂时无法读取玩家资料。"
        print(f"[chat_tool] read_player_info result={result!r}")
        return result

    with SyncSessionLocal() as session:
        player = _query_player(session, player_id)

    if player is None:
        result = f"暂未找到玩家 {player_id} 的资料。"
        print(f"[chat_tool] read_player_info result={result!r}")
        return result

    result = (
        f"玩家{player.name}（ID：{player.id}，账号：{player.account}），"
        f"等级：{player.level}，金币：{player.gold}。"
    )
    print(f"[chat_tool] read_player_info result={result!r}")
    return result


def read_player_farm_info(player_id: str) -> str:
    """读取当前玩家可查看的作物与种植概况。"""
    print(f"[chat_tool] read_player_farm_info start player_id={player_id!r}")
    with SyncSessionLocal() as session:
        player = _query_player(session, player_id)
        crops = session.query(Crop).order_by(Crop.id.asc()).all()
        instances = (
            session.query(
                CropInstance.index.label("index"),
                CropInstance.planted_at,
                CropInstance.water,
                CropInstance.fertility,
                CropInstance.temperature,
                Crop.name.label("crop_name"),
                Crop.growth_seconds,
                Crop.price,
                Crop.description,
                Crop.profit_price,
            )
            .join(Crop, Crop.id == CropInstance.crop_id)
            .order_by(CropInstance.index.asc())
            .all()
        )

    print(
        "[chat_tool] read_player_farm_info db "
        f"player_found={player is not None} crop_count={len(crops)} instance_count={len(instances)}"
    )
    if not crops:
        result = "当前还没有初始化任何作物数据。"
        print(f"[chat_tool] read_player_farm_info result={result!r}")
        return result

    owner_name = player.name if player is not None else (player_id if player_id else "当前玩家")
    parts = [f"{owner_name}当前可查看 {len(instances)} 个正在生长的作物实例。"]
    if instances:
        growing = []
        for instance in instances[:5]:
            remain_seconds = _calc_remain_growth_seconds(
                planted_at=instance.planted_at,
                growth_seconds=instance.growth_seconds,
            )
            status = "可收获" if remain_seconds <= 0 else f"预计还需 {remain_seconds} 秒成熟"
            growing.append(
                f"{instance.index} 号位种着{instance.crop_name}，"
                f"{status}，水分{instance.water:.1f}、养分{instance.fertility:.1f}、温度{instance.temperature:.1f}℃"
            )
        suffix = f"；另有 {len(instances) - 5} 个作物实例未展示" if len(instances) > 5 else ""
        parts.append("当前种植状态：" + "；".join(growing) + suffix + "。")
    else:
        parts.append("当前还没有正在生长的作物。")

    crop_options = []
    for crop in crops:
        crop_options.append(
            f"{crop.name}（成本{crop.price}，成熟约{crop.growth_seconds}秒，收获价值{crop.profit_price}）"
        )
    parts.append("可种作物：" + "；".join(crop_options) + "。")
    result = "".join(parts)
    print(f"[chat_tool] read_player_farm_info result={result!r}")
    return result


def _calc_remain_growth_seconds(*, planted_at: datetime, growth_seconds: int) -> int:
    """按 CropInstance 的种植时间和 Crop 的生长时长计算剩余成熟时间。"""
    elapsed_seconds = max(0, int((datetime.now() - planted_at).total_seconds()))
    return max(0, growth_seconds - elapsed_seconds)
