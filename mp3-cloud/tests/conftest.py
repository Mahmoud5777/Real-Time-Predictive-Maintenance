"""Tests locaux ; --postgres active les tests dans une base unique et jetable.

Le compte configure par DATABASE_URL doit pouvoir creer des bases. Aucune migration
descendante ni suppression de donnees n'est effectuee sur fog_cloud.
"""

import asyncio
import re
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from sqlalchemy import pool
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from alembic import command
from alembic.config import Config
from app.config import settings
from app.db.catalogue import initialize_catalogue

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--postgres",
        action="store_true",
        help="Creer une base PostgreSQL jetable et executer les tests d'integration.",
    )
    parser.addoption(
        "--mqtt", action="store_true",
        help="Tests MQTT avec broker Docker et PostgreSQL jetables (implique --postgres).",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        if "postgres" in item.keywords and not (
            config.getoption("--postgres") or config.getoption("--mqtt")
        ):
            item.add_marker(pytest.mark.skip(reason="Tests PostgreSQL : relancer avec --postgres."))
        if "mqtt" in item.keywords and not config.getoption("--mqtt"):
            item.add_marker(pytest.mark.skip(reason="Tests MQTT : relancer avec --mqtt."))


@dataclass(frozen=True)
class PostgresDatabase:
    name: str
    url: URL = field(repr=False)

    def alembic_config(self) -> Config:
        config = Config(str(PROJECT_ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
        config.attributes["database_url"] = self.url.render_as_string(hide_password=False)
        return config


async def _manage_test_database(database: PostgresDatabase, *, create: bool) -> None:
    # Nom genere ici uniquement ; ne jamais accepter le nom d'une base utilisateur.
    if re.fullmatch(r"mp3_test_[0-9a-f]{32}", database.name) is None:
        raise ValueError("Refusing to manage a database outside the disposable test namespace")
    admin_url = database.url.set(drivername="postgresql", database="postgres")
    connection = await asyncpg.connect(admin_url.render_as_string(hide_password=False), timeout=10)
    try:
        if create:
            await connection.execute(f'CREATE DATABASE "{database.name}"')
        else:
            await connection.execute(f'DROP DATABASE "{database.name}" WITH (FORCE)')
    finally:
        await connection.close()


@pytest.fixture(scope="session")
def postgres_database(pytestconfig: pytest.Config) -> Iterator[PostgresDatabase]:
    if not (pytestconfig.getoption("--postgres") or pytestconfig.getoption("--mqtt")):
        pytest.skip("Tests PostgreSQL : relancer avec --postgres.")
    source = make_url(settings.database_url)
    if source.drivername != "postgresql+asyncpg":
        pytest.fail("--postgres requires a PostgreSQL asyncpg DATABASE_URL")
    name = f"mp3_test_{uuid4().hex}"
    database = PostgresDatabase(name, source.set(database=name))
    asyncio.run(_manage_test_database(database, create=True))
    try:
        command.upgrade(database.alembic_config(), "head")
        yield database
    finally:
        asyncio.run(_manage_test_database(database, create=False))


@pytest_asyncio.fixture
async def db_session(postgres_database: PostgresDatabase) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(postgres_database.url, poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                async with AsyncSession(
                    bind=connection,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                ) as session:
                    yield session
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.fixture
def committed_postgres_database(postgres_database: PostgresDatabase) -> Iterator[PostgresDatabase]:
    """Base distincte pour les tests multi-connexions et de commit HTTP reel.

    Ses commits ne peuvent pas affecter la base utilisee par les tests de l'etape 2.
    """
    name = f"mp3_test_{uuid4().hex}"
    database = PostgresDatabase(name, postgres_database.url.set(database=name))
    asyncio.run(_manage_test_database(database, create=True))
    try:
        command.upgrade(database.alembic_config(), "head")
        yield database
    finally:
        asyncio.run(_manage_test_database(database, create=False))


@pytest_asyncio.fixture
async def populated_session(db_session: AsyncSession) -> AsyncIterator[AsyncSession]:
    await initialize_catalogue(db_session)
    yield db_session


@pytest.fixture(autouse=True)
def _force_ingest_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixe le token d ingestion pour que les tests ne dependent jamais du `.env` local."""
    monkeypatch.setattr(settings, "ingest_token", "test-token", raising=False)
