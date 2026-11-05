"""Initialise FOG_A/B/C et M01..M12, apres alembic upgrade head.

Depuis mp3-cloud : python -m scripts.init_catalogue
Une nouvelle execution conserve les entrees et les observations existantes.
"""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.catalogue import initialize_catalogue


async def main() -> None:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions.begin() as session:
            result = await initialize_catalogue(session)
        print(f"Catalogue : {result.fog_total} Fog, {result.machines_total} machines.")
        print(f"Ajouts : {result.fog_inserted} Fog, {result.machines_inserted} machines.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
