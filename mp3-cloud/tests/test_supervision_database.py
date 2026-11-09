"""Loss, recovery, retained data, concurrent ingestion and rollback on disposable DBs."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
import pytest_asyncio
import yaml
from httpx import ASGITransport, AsyncClient
from openapi_schema_validator import OAS30Validator
from sqlalchemy import insert, select, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from test_read_database import expand_refs

from alembic import command
from app.config import Settings
from app.db.catalogue import initialize_catalogue
from app.db.session import get_session
from app.main import create_app
from app.models.tables import FogNode, FogStatusHistory, Prediction
from app.schemas.messages import PredictionResult
from app.services.ingest import persist_batch
from app.supervision.service import check_nodes
from scripts.export_openapi import CONTRACT

pytestmark = pytest.mark.postgres
AT = datetime(2026, 11, 7, 10, tzinfo=UTC)
CONFIG = Settings(_env_file=None)
FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures" / "valid"


@pytest_asyncio.fixture
async def factory(committed_postgres_database):
    engine = create_async_engine(committed_postgres_database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        await initialize_catalogue(session)
    try:
        yield factory
    finally:
        await engine.dispose()


def at(seconds):
    return AT + timedelta(seconds=seconds)


async def heartbeat(factory, seconds=0, *, producer=None, status="ONLINE", item=None):
    if item is None:
        item = json.loads((FIXTURES / "fog_status_ok.json").read_text(encoding="utf-8"))
        item["payload"].update(
            message_id=f"supervision-heart-{uuid4().hex}",
            status=status,
            last_heartbeat=at(seconds if producer is None else producer).isoformat(),
        )

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return at(seconds)

    with patch("app.services.ingest.datetime", Clock):
        async with factory() as session:
            report = await persist_batch(session, [item])
    return item, report


async def state(factory):
    async with factory() as session:
        return await session.get(FogNode, "FOG_A")


async def history(factory):
    async with factory() as session:
        return (
            (
                await session.execute(
                    select(FogStatusHistory)
                    .where(FogStatusHistory.record_type == "SUPERVISION")
                    .order_by(FogStatusHistory.id)
                )
            )
            .scalars()
            .all()
        )


async def tick(factory, seconds):
    return await check_nodes(factory, CONFIG, now=at(seconds))


async def test_unobserved_nodes_remain_unknown_without_fake_history(factory):
    assert await tick(factory, 0) == 0
    assert await tick(factory, 100) == 0
    node = await state(factory)
    assert node.status == "OFFLINE" and node.supervision_status == "UNKNOWN"
    assert node.last_heartbeat is None and node.supervision_since is None
    assert node.supervision_checked_at == at(100) and await history(factory) == []


async def test_loss_and_recovery_are_persistent_idempotent_and_keep_reported_state(factory):
    await heartbeat(factory)
    assert await tick(factory, 0) == 1
    assert await tick(factory, 15) == 0
    assert await tick(factory, 16) == 1
    node = await state(factory)
    assert node.status == "ONLINE" and node.supervision_status == "UNREACHABLE"
    assert node.offline_since is None and node.recovered_at is None
    assert node.supervision_since == at(16)
    assert await tick(factory, 17) == 0
    await heartbeat(factory, 18, status="OVERLOADED")
    assert await tick(factory, 19) == 1
    rows = await history(factory)
    assert [r.supervision_status for r in rows] == ["REACHABLE", "UNREACHABLE", "REACHABLE"]
    assert rows[-1].previous_supervision_status == "UNREACHABLE"
    assert rows[-1].evidence_received_at == at(18)
    assert all(r.status is None and r.cpu_percent is None and r.ram_percent is None for r in rows)
    assert (await state(factory)).status == "OVERLOADED"


async def test_late_and_duplicate_heartbeats_do_not_revive_a_silent_node(factory):
    item, _ = await heartbeat(factory)
    await tick(factory, 0)
    await tick(factory, 16)
    _, report = await heartbeat(factory, 18, item=item)
    assert report.duplicates == 1
    assert (await state(factory)).last_received_at == AT
    assert await tick(factory, 19) == 0
    # New message identity but old producer date: stored as raw observation only.
    await heartbeat(factory, 20, producer=-1)
    assert await tick(factory, 21) == 0
    assert (await state(factory)).supervision_status == "UNREACHABLE"


async def test_retained_first_heartbeat_is_not_fresh_and_reported_offline_is_distinct(factory):
    await heartbeat(factory, 0, producer=-60)
    await tick(factory, 0)
    assert (await state(factory)).supervision_reason == "HEARTBEAT_TIMEOUT"
    await heartbeat(factory, 1, status="OFFLINE")
    await tick(factory, 1)
    assert (await state(factory)).supervision_reason == "REPORTED_OFFLINE"


async def test_future_clock_is_unknown_and_corrected_clock_can_recover_projection(factory):
    await heartbeat(factory, 0, producer=3600)
    await tick(factory, 0)
    assert (await state(factory)).supervision_reason == "CLOCK_SKEW"
    await heartbeat(factory, 1, producer=-100)  # delayed old data cannot correct the projection
    assert (await state(factory)).last_heartbeat == at(3600)
    await heartbeat(factory, 1)  # corrected producer clock, earlier than poisoned projection
    await tick(factory, 1)
    node = await state(factory)
    assert node.last_heartbeat == at(1) and node.supervision_status == "REACHABLE"


async def test_monitor_gap_is_unknown_coverage_and_not_backdated_failure(factory):
    await heartbeat(factory)
    await tick(factory, 0)
    assert await tick(factory, 31) == 2
    rows = await history(factory)
    assert rows[-2].supervision_status == "UNKNOWN"
    assert rows[-2].supervision_reason == "MONITOR_GAP"
    assert (rows[-2].gap_start, rows[-2].gap_end) == (AT, at(31))
    assert rows[-1].supervision_reason == "HEARTBEAT_TIMEOUT"
    assert rows[-1].observed_at == at(31) and (await state(factory)).supervision_since == at(31)
    assert await tick(factory, 32) == 0


async def test_clock_rollback_does_not_change_history_or_checked_time(factory):
    await heartbeat(factory)
    await tick(factory, 0)
    assert await tick(factory, -10) == 0
    assert (await state(factory)).supervision_checked_at == AT
    assert len(await history(factory)) == 1


async def test_concurrent_supervisors_create_only_one_transition(factory):
    await heartbeat(factory)
    assert sorted(await asyncio.gather(tick(factory, 0), tick(factory, 0))) == [0, 1]
    assert len(await history(factory)) == 1


async def test_ingestion_lock_serializes_scan_and_fresh_heartbeat_wins(factory):
    await heartbeat(factory)
    await tick(factory, 0)
    # Hold the same lock as ingestion while a scan is pending, then commit a fresh projection.
    async with factory() as writer, writer.begin():
        await writer.execute(
            select(FogNode).where(FogNode.fog_id == "FOG_A").with_for_update(key_share=True)
        )
        scanning = asyncio.create_task(tick(factory, 20))
        await writer.execute(
            update(FogNode)
            .where(FogNode.fog_id == "FOG_A")
            .values(last_heartbeat=at(20), last_received_at=at(20))
        )
    assert await scanning == 0
    assert (await state(factory)).supervision_status == "REACHABLE"


@pytest.mark.parametrize("operation", ["scan", "heartbeat"])
async def test_fog_updates_do_not_wait_for_uncommitted_prediction_reference(factory, operation):
    """Une FK de prediction protege la cle Fog, sans bloquer ses champs non clefs."""
    await heartbeat(factory)
    payload = json.loads((FIXTURES / "prediction_ok.json").read_text(encoding="utf-8"))[
        "payload"
    ]
    prediction = PredictionResult.model_validate(payload).model_dump()
    async with factory() as writer, writer.begin():
        # Le vrai INSERT prend FOR KEY SHARE sur FOG_A jusqu'au commit du lot.
        await writer.execute(insert(Prediction).values(**prediction))
        if operation == "scan":
            config = CONFIG.model_copy(update={"supervision_database_timeout_seconds": 1})
            assert await check_nodes(factory, config, now=AT) == 1
        else:
            async with asyncio.timeout(1):
                _message, result = await heartbeat(factory, 1)
            assert result.accepted == 1 and result.rejected == 0
    assert (await state(factory)).last_heartbeat == at(1 if operation == "heartbeat" else 0)


@pytest.mark.parametrize(
    "failure", [DBAPIError("SQL", {}, Exception("failure")), asyncio.CancelledError()]
)
async def test_failed_state_update_rolls_back_inserted_history(factory, failure):
    await heartbeat(factory)
    with patch("app.supervision.service.update", side_effect=failure), pytest.raises(type(failure)):
        await tick(factory, 0)
    assert await history(factory) == []
    assert (await state(factory)).supervision_checked_at is None
    assert await tick(factory, 0) == 1


async def test_lock_timeout_preserves_state_and_later_scan_recovers(factory):
    await heartbeat(factory)
    config = CONFIG.model_copy(update={"supervision_database_timeout_seconds": 0.2})
    async with factory() as writer, writer.begin():
        await writer.execute(select(FogNode).where(FogNode.fog_id == "FOG_A").with_for_update())
        with pytest.raises((TimeoutError, DBAPIError)):
            await check_nodes(factory, config, now=AT)
    assert await history(factory) == [] and await tick(factory, 0) == 1


async def test_http_separates_reported_history_and_supervision_with_filters(factory):
    await heartbeat(factory)
    await tick(factory, 0)
    await tick(factory, 16)
    app = create_app()

    async def session_override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.get("/api/v1/fog/status-history")
        assert response.status_code == 200 and response.json()["meta"]["total"] == 1
        assert response.json()["items"][0]["record_type"] == "HEARTBEAT"
        response = await client.get(
            "/api/v1/fog/supervision-history",
            params={
                "fog_id": "FOG_A",
                "supervision_status": "UNREACHABLE",
                "limit": 1,
                "from": at(15).isoformat(),
                "to": at(16).isoformat(),
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert (
            body["meta"]["total"] == 1
            and body["items"][0]["supervision_reason"] == "HEARTBEAT_TIMEOUT"
        )
        schema = contract["paths"]["/fog/supervision-history"]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]
        OAS30Validator(expand_refs(schema, contract)).validate(body)
        response = await client.get(
            "/api/v1/fog/nodes", params={"supervision_status": "UNREACHABLE"}
        )
        assert response.json()["meta"]["total"] == 1
        assert response.json()["items"][0]["status"] == "ONLINE"
        # Fixed old clock means persisted supervision is now stale in a live HTTP read.
        assert response.json()["items"][0]["effective_supervision_status"] == "UNKNOWN"


async def test_history_shape_enforced_by_database(factory):
    async with factory() as session:
        with pytest.raises(IntegrityError):
            async with session.begin():
                await session.execute(
                    insert(FogStatusHistory).values(
                        message_id="invalid-cloud-record",
                        fog_id="FOG_A",
                        zone="A",
                        observed_at=AT,
                        record_type="SUPERVISION",
                        status="ONLINE",
                        supervision_status="REACHABLE",
                        previous_supervision_status="UNKNOWN",
                        supervision_reason="FRESH_HEARTBEAT",
                        timeout_seconds=15,
                    )
                )


def test_downgrade_refuses_loss_of_supervision_records(committed_postgres_database):
    async def record():
        engine = create_async_engine(committed_postgres_database.url, poolclass=NullPool)
        factory = async_sessionmaker(engine)
        try:
            async with factory() as session, session.begin():
                await initialize_catalogue(session)
                await session.execute(
                    update(FogNode)
                    .where(FogNode.fog_id == "FOG_A")
                    .values(
                        status="ONLINE",
                        last_heartbeat=AT,
                        last_received_at=AT,
                    )
                )
            assert await check_nodes(factory, CONFIG, now=AT) == 1
        finally:
            await engine.dispose()

    asyncio.run(record())
    config = committed_postgres_database.alembic_config()
    with pytest.raises(RuntimeError, match="Downgrade refused"):
        command.downgrade(config, "0002_kpi_scope")
    command.check(config)
