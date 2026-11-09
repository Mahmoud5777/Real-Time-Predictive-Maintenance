"""Validate public windows, honest missing data and worker recovery without a DB."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.analytics.windows import closed_hour, validate_window
from app.analytics.worker import Worker
from app.config import Settings
from app.db.session import get_session
from app.main import create_app

AT = datetime(2026, 11, 7, 10, tzinfo=UTC)
HOUR = timedelta(hours=1)
ROUTES = ["/kpis", "/measurements", "/model-comparison", "/risk-ranking"]


def test_windows_normalize_utc_and_allow_only_closed_hours():
    assert closed_hour(AT + timedelta(minutes=40)) == AT
    assert validate_window(AT, AT + HOUR, AT + HOUR) == (AT, AT + HOUR)
    assert (
        validate_window(datetime.fromisoformat("2026-11-07T11:00:00+01:00"), AT + HOUR, AT + HOUR)[
            0
        ]
        == AT
    )


@pytest.mark.parametrize(
    "start,end",
    [
        (AT.replace(tzinfo=None), AT + HOUR),
        (AT, AT),
        (AT + HOUR, AT),
        (AT + timedelta(seconds=1), AT + HOUR),
        (AT, AT + 2 * HOUR),
        (AT - 744 * HOUR, AT + HOUR),
    ],
)
def test_invalid_windows(start, end):
    with pytest.raises(ValueError):
        validate_window(start, end, AT + HOUR)


@pytest.mark.parametrize(
    "changes",
    [
        {"kpi_refresh_seconds": 0},
        {"kpi_lookback_hours": 0},
        {"kpi_database_timeout_seconds": 0},
        {"raw_retention_days": 0},
        {"kpi_metrics_port": 65536},
        {"kpi_lookback_hours": 25, "raw_retention_days": 1},
    ],
)
def test_worker_config_is_bounded(changes):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **changes)


@pytest.fixture
def client():
    app = create_app()
    session = AsyncMock()

    async def database():
        yield session

    app.dependency_overrides[get_session] = database
    with TestClient(app) as http:
        yield http, session


@pytest.mark.parametrize("path", ROUTES)
@pytest.mark.parametrize(
    "params",
    [
        {"from": "2026-11-07T10:00:00"},
        {"to": "bad"},
        {"from": "2026-11-01T10:01:00Z"},
        {"limit": 1001},
        {"offset": -1},
        {"from": "2026-10-01T00:00:00Z", "to": "2026-11-02T00:00:00Z"},
        {"from": "2026-11-02T00:00:00Z", "to": "2026-11-01T00:00:00Z"},
    ],
)
def test_invalid_analytics_never_execute_sql(client, path, params):
    http, session = client
    assert http.get("/api/v1/analytics" + path, params=params).status_code == 422
    session.execute.assert_not_awaited()


@pytest.mark.parametrize(
    "path,params",
    [
        ("/kpis", {"scope": "zone", "scope_value": "D"}),
        ("/kpis", {"scope": "machine", "scope_value": "M99"}),
        ("/kpis", {"scope": "fog", "scope_value": "FOG_D"}),
        ("/kpis", {"metric": "made_up"}),
        ("/kpis", {"scope": "invalid"}),
        ("/measurements", {"scope": "model"}),
        ("/model-comparison", {"model_version": "v" * 65}),
        ("/risk-ranking", {"from": "2026-11-01T00:00:00Z", "to": "2026-11-02T00:00:00Z"}),
    ],
)
def test_invalid_dimensions(client, path, params):
    http, session = client
    assert http.get("/api/v1/analytics" + path, params=params).status_code == 422
    session.execute.assert_not_awaited()


@pytest.mark.parametrize("path", ROUTES)
def test_db_failure_is_safe_503(client, path):
    http, session = client
    session.execute.side_effect = OperationalError("private SQL", {}, Exception("private DSN"))
    response = http.get("/api/v1/analytics" + path)
    assert response.status_code == 503
    assert response.json()["status"] == 503 and "private" not in response.text


async def test_worker_recovers_and_only_reports_success_after_commit(caplog):
    refresh = AsyncMock(side_effect=[OperationalError("SQL", {}, Exception("SECRET")), None, 12])
    worker = Worker(None, Settings(_env_file=None), refresh_fn=refresh)
    assert not await worker.run_once()
    assert worker.ready._value.get() == 0
    assert worker.last_success._value.get() == 0
    assert "SECRET" not in caplog.text
    assert not await worker.run_once()  # competing writer owns the lock
    assert await worker.run_once()
    assert worker.ready._value.get() == 1 and worker.rows._value.get() == 12
    assert worker.last_success._value.get() > 0


async def test_worker_cancellation_is_not_swallowed():
    worker = Worker(
        None, Settings(_env_file=None), refresh_fn=AsyncMock(side_effect=asyncio.CancelledError)
    )
    with pytest.raises(asyncio.CancelledError):
        await worker.run_once()


async def test_worker_stops_without_another_refresh():
    stop = asyncio.Event()

    async def refresh(*_):
        stop.set()
        return 0

    worker = Worker(None, Settings(_env_file=None), refresh_fn=refresh)
    await asyncio.wait_for(worker.run(stop), timeout=1)
    assert worker.ready._value.get() == 0
