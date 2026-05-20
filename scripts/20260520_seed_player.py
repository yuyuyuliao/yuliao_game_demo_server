from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.command.database import DB_PATH, build_database_url, create_session_factory, init_db_async
from app.model import Player


async def seed_player(db_path: Path) -> None:
    """Insert the default demo player if player id=1 does not already exist."""
    await init_db_async(db_path)
    engine = create_async_engine(build_database_url(db_path), future=True)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            existing_player = await session.get(Player, 1)
            if existing_player is not None:
                return

            session.add(
                Player(
                    id=1,
                    name="Player 1",
                    account="player1",
                    password="demo-password-hash",
                    gold=0,
                    level=1,
                )
            )
            await session.commit()
    finally:
        await engine.dispose()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Insert default player id=1")
    parser.add_argument("--db-path", type=Path, default=DB_PATH)
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    asyncio.run(seed_player(args.db_path))


if __name__ == "__main__":
    main()
