from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import create_async_engine

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.command.database import DB_PATH, build_database_url, create_session_factory, init_db_async
from app.model import Crop, LandPlot


def _default_lands() -> list[LandPlot]:
    """返回农场默认土地数据。"""
    return [
        LandPlot(price=100, name="普通黄土地", description="最基础的农田土壤，结构略显粗糙，但依然能够稳定种植作物。",
                 level=1,
                 growth_multiplier=1.00),

        LandPlot(price=180, name="松软耕土", description="经过翻耕和整理后的土地，土壤更加松软，作物更容易扎根生长。",
                 level=2,
                 growth_multiplier=1.05),

        LandPlot(price=320, name="肥沃黑土", description="富含有机质的黑色土壤，养分充足，是优质农田的标志。",
                 level=3,
                 growth_multiplier=1.10),

        LandPlot(price=560, name="陈年熟土", description="经过多年耕种形成的成熟土壤，结构稳定，作物生长更加顺利。",
                 level=4,
                 growth_multiplier=1.18),

        LandPlot(price=960, name="富养沃土", description="养分极为充足的优质土壤，几乎所有作物都能在这里快速生长。",
                 level=5,
                 growth_multiplier=1.28),

        LandPlot(price=1650, name="黄金沃土", description="极为稀有的顶级农田土壤，松软肥沃，被农夫们称为“会呼吸的土地”。",
                 level=6, growth_multiplier=1.40),
    ]


def _default_crops() -> list[Crop]:
    """返回农场默认作物数据。"""
    return [
        Crop(name="胡萝卜", growth_seconds=3600, price=30,
             description="一根非常努力的胡萝卜。它的梦想其实不是被吃掉，而是成为一根巨型胡萝卜，不过目前还在努力练习长大。",
             profit_price=50),

        Crop(name="土豆", growth_seconds=4200, price=45,
             description="土豆大多数时间都躲在土里思考人生。有人怀疑它其实是在睡觉，但土豆本人对此拒绝回应。",
             profit_price=70),

        Crop(name="草莓", growth_seconds=5400, price=70,
             description="草莓总觉得自己是水果界的明星。唯一的问题是，附近的小动物似乎也这么认为。",
             profit_price=100),

        Crop(name="玉米", growth_seconds=7200, price=90,
             description="玉米喜欢和同伴排成整齐的一排，看起来像一支严肃的队伍。不过只要风一吹，它们就会集体开始聊天。",
             profit_price=130),

        Crop(name="蓝莓", growth_seconds=8400, price=110,
             description="蓝莓看起来像一颗颗小星星。农夫曾试图数清楚一株有多少颗，但数到一半就忍不住吃掉了几颗。",
             profit_price=160),

        Crop(name="南瓜", growth_seconds=10800, price=140,
             description="南瓜藤总喜欢到处乱爬，好像农场都是它家的。有一年长出了一颗特别大的南瓜，大家决定暂时不要惹它。",
             profit_price=210),
    ]


async def seed_farm_data(db_path: Path) -> None:
    """向数据库按需写入农场默认数据。"""
    await init_db_async(db_path)
    engine = create_async_engine(build_database_url(db_path), future=True)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            land_count = await session.scalar(select(func.count()).select_from(LandPlot))
            if land_count == 0:
                session.add_all(_default_lands())

            crop_count = await session.scalar(select(func.count()).select_from(Crop))
            if crop_count == 0:
                session.add_all(_default_crops())

            await session.commit()
    finally:
        await engine.dispose()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="写入农场默认数据")
    parser.add_argument("--db-path", type=Path, default=DB_PATH)
    return parser.parse_args(argv)


def main() -> None:
    """解析命令行参数并执行默认数据写入。"""
    args = parse_args()
    asyncio.run(seed_farm_data(args.db_path))


if __name__ == "__main__":
    main()
