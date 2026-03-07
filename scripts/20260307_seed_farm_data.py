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

from app.command.database import build_database_url, create_session_factory, init_db_async
from app.model import Crop, LandPlot


def _default_lands() -> list[LandPlot]:
    """返回农场默认土地数据。"""
    return [
        LandPlot(price=100, description="1号地：靠近小溪，土壤松软。", level=1, growth_multiplier=1.00),
        LandPlot(price=180, description="2号地：有石板路，适合新手。", level=1, growth_multiplier=1.00),
        LandPlot(price=300, description="3号地：老农留下的试验田。", level=2, growth_multiplier=1.10),
        LandPlot(price=480, description="4号地：向阳高地，温度更稳定。", level=2, growth_multiplier=1.10),
        LandPlot(price=720, description="5号地：微风谷地，生长速度更快。", level=3, growth_multiplier=1.20),
        LandPlot(price=1020, description="6号地：传说中的金色土壤。", level=4, growth_multiplier=1.30),
    ]


def _default_crops() -> list[Crop]:
    """返回农场默认作物数据。"""
    return [
        Crop(name="胡萝卜", growth_seconds=3600, price=30, description="成长稳定，适合练手。"),
        Crop(name="玉米", growth_seconds=7200, price=60, description="成熟后收益更高。"),
        Crop(name="草莓", growth_seconds=5400, price=80, description="甜度高但对水量要求更高。"),
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


def main() -> None:
    """解析命令行参数并执行默认数据写入。"""
    parser = argparse.ArgumentParser(description="写入农场默认数据")
    parser.add_argument("--db-path", type=Path, default=REPO_ROOT / "app" / "data" / "chat.db")
    args = parser.parse_args()
    asyncio.run(seed_farm_data(args.db_path))


if __name__ == "__main__":
    main()
