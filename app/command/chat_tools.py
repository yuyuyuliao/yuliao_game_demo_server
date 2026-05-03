from __future__ import annotations

from sqlalchemy import create_engine, or_
from sqlalchemy.orm import Session, sessionmaker

from app.command.database import DB_PATH
from app.model import Crop, CropInstance, LandPlot, Player

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
    if not player_id:
        return "未提供玩家标识，暂时无法读取玩家资料。"

    with SyncSessionLocal() as session:
        player = _query_player(session, player_id)

    if player is None:
        return f"暂未找到玩家 {player_id} 的资料。"

    return (
        f"玩家{player.name}（ID：{player.id}，账号：{player.account}），"
        f"等级：{player.level}，金币：{player.gold}。"
    )


def read_player_farm_info(player_id: str) -> str:
    """读取当前玩家可查看的田地概况。"""
    with SyncSessionLocal() as session:
        player = _query_player(session, player_id)
        lands = session.query(LandPlot).order_by(LandPlot.id.asc()).all()
        instances = {
            row.index: row
            for row in (
                session.query(
                    CropInstance.index.label("index"),
                    Crop.name.label("crop_name"),
                    CropInstance.water,
                    CropInstance.fertility,
                    CropInstance.temperature,
                )
                .outerjoin(Crop, Crop.id == CropInstance.crop_id)
                .all()
            )
        }

    if not lands:
        return "当前还没有初始化任何田地数据。"

    owner_name = player.name if player is not None else (player_id if player_id else "当前玩家")
    planted_rows = []
    for index, land in enumerate(lands, start=1):
        instance = instances.get(index)
        if instance is None or not instance.crop_name:
            continue
        planted_rows.append((land, instance))

    empty_count = len(lands) - len(planted_rows)
    parts = [
        f"{owner_name}当前可查看 {len(lands)} 块田地，"
        f"其中 {len(planted_rows)} 块已种植，{empty_count} 块空闲。"
    ]
    if planted_rows:
        samples = []
        for land, instance in planted_rows[:3]:
            samples.append(
                f"{land.name}正在种植{instance.crop_name}，"
                f"水分{instance.water:.1f}、肥力{instance.fertility:.1f}、温度{instance.temperature:.1f}℃"
            )
        parts.append("已种植地块：" + "；".join(samples))
    else:
        parts.append("当前所有田地都还没有种下作物。")

    parts.append("演示服暂未区分个人土地归属，以上为该玩家当前可查看的农场概况。")
    return "".join(parts)
