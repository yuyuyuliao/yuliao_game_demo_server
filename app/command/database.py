from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

import aiosqlite
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.model import BaseModel, Crop, LandPlot

APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "chat.db"
CHROMA_PATH = str(DATA_DIR / "chroma")
MIGRATIONS_DIR = APP_DIR / "migrations"
MIGRATION_FILE_GLOB = "[0-9][0-9][0-9]_*.sql"
MIGRATION_NAME_PATTERN = re.compile(r"^(?P<version>\d{3})_.+\.sql$")
logger = logging.getLogger(__name__)


def build_database_url(db_path: Path = DB_PATH) -> str:
    """构建异步 SQLite 连接地址。"""
    return f"sqlite+aiosqlite:///{db_path}"


def create_session_factory(engine: AsyncEngine) -> sessionmaker:
    """基于异步引擎创建会话工厂。"""
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


ENGINE = create_async_engine(build_database_url(), future=True)
AsyncSessionLocal = create_session_factory(ENGINE)


def _migration_files() -> list[Path]:
    """按版本顺序返回迁移文件。"""
    return sorted(MIGRATIONS_DIR.glob(MIGRATION_FILE_GLOB))


def _migration_version(migration_file: Path) -> int:
    """解析迁移文件版本号。"""
    match = MIGRATION_NAME_PATTERN.fullmatch(migration_file.name)
    if match is None:
        raise ValueError(
            f"invalid migration filename '{migration_file.name}': "
            f"expected format '{MIGRATION_FILE_GLOB}'"
        )
    return int(match.group("version"))


def _initial_migration_version() -> int | None:
    """返回首个迁移版本号。"""
    migration_files = _migration_files()
    if not migration_files:
        return None
    return _migration_version(migration_files[0])


def _required_tables() -> tuple[str, ...]:
    """返回当前 ORM 已注册的关键表。"""
    return tuple(BaseModel.metadata.tables)


def _temporary_engine(db_path: Path) -> AsyncEngine:
    """为非默认数据库路径创建临时引擎。"""
    return create_async_engine(build_database_url(db_path), future=True)


async def _run_migrations_async(db_path: Path) -> None:
    """执行尚未应用的 SQLite 迁移脚本。"""
    migration_files = _migration_files()
    async with aiosqlite.connect(db_path) as conn:
        row = await (await conn.execute("PRAGMA user_version")).fetchone()
        current_version = row[0]
        table_rows = await (
            await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ).fetchall()
        existing_tables = {table_row[0] for table_row in table_rows}
        missing_tables = sorted(set(_required_tables()) - existing_tables)
        if current_version > 0 and missing_tables:
            initial_version = _initial_migration_version()
            if initial_version is not None and current_version == initial_version:
                logger.warning(
                    "Database at user_version=%s is missing key tables %s; re-running initial migration.",
                    current_version,
                    ", ".join(missing_tables),
                )
                current_version = 0
            else:
                missing_tables_str = ", ".join(missing_tables)
                raise RuntimeError(
                    f"database schema is inconsistent at user_version={current_version}: "
                    f"missing tables: {missing_tables_str}; automatic repair only supports "
                    f"the initial migration version {initial_version}"
                )
        for migration_file in migration_files:
            version = _migration_version(migration_file)
            if version <= current_version:
                continue
            sql = migration_file.read_text(encoding="utf-8")
            await conn.executescript(sql)
            await conn.execute(f"PRAGMA user_version = {version:d}")
        await conn.commit()


async def run_migrations(db_path: Path = DB_PATH) -> None:
    """执行数据库迁移。"""
    await _run_migrations_async(db_path)


async def _seed_initial_data_async(session_factory: sessionmaker) -> None:
    """初始化基础种地配置数据。"""
    async with session_factory() as session:
        land_count = await session.scalar(select(func.count()).select_from(LandPlot))
        if land_count == 0:
            session.add_all(
                [
                    LandPlot(price=100, description="1号地：靠近小溪，土壤松软。", level=1, growth_multiplier=1.00),
                    LandPlot(price=180, description="2号地：有石板路，适合新手。", level=1, growth_multiplier=1.00),
                    LandPlot(price=300, description="3号地：老农留下的试验田。", level=2, growth_multiplier=1.10),
                    LandPlot(price=480, description="4号地：向阳高地，温度更稳定。", level=2, growth_multiplier=1.10),
                    LandPlot(price=720, description="5号地：微风谷地，生长速度更快。", level=3, growth_multiplier=1.20),
                    LandPlot(price=1020, description="6号地：传说中的金色土壤。", level=4, growth_multiplier=1.30),
                ]
            )
        crop_count = await session.scalar(select(func.count()).select_from(Crop))
        if crop_count == 0:
            session.add_all(
                [
                    Crop(name="胡萝卜", growth_seconds=3600, price=30, description="成长稳定，适合练手。"),
                    Crop(name="玉米", growth_seconds=7200, price=60, description="成熟后收益更高。"),
                    Crop(name="草莓", growth_seconds=5400, price=80, description="甜度高但对水量要求更高。"),
                ]
            )
        await session.commit()


async def init_db_async(db_path: Path = DB_PATH) -> None:
    """通过迁移初始化数据库，并补齐基础种子数据。"""
    await run_migrations(db_path)
    temp_engine: AsyncEngine | None = None
    if db_path == DB_PATH:
        session_factory = AsyncSessionLocal
    else:
        temp_engine = _temporary_engine(db_path)
        session_factory = create_session_factory(temp_engine)
    try:
        await _seed_initial_data_async(session_factory)
    finally:
        if temp_engine is not None:
            await temp_engine.dispose()


def init_db(db_path: Path = DB_PATH) -> None:
    """兼容同步调用方式的数据库初始化入口。"""
    asyncio.run(init_db_async(db_path))
