"""Reachability rules, freshness and bounded worker failures without external services."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.api.fog import with_heartbeat_age
from app.config import Settings
from app.schemas.reads import FogNodeRead
from app.supervision.service import classify
from app.supervision.worker import Worker

AT = datetime(2026, 11, 7, 10, tzinfo=UTC)
CONFIG = Settings(_env_file=None)


@pytest.mark.parametrize(
    "heartbeat,receipt,status,expected",
    [
        (None, None, "OFFLINE", ("UNKNOWN", "NO_HEARTBEAT")),
        (0, None, "ONLINE", ("UNKNOWN", "NO_HEARTBEAT")),
        (0, 0, "ONLINE", ("REACHABLE", "FRESH_HEARTBEAT")),
        (0, 0, "OVERLOADED", ("REACHABLE", "FRESH_HEARTBEAT")),
        (0, 0, "RECOVERING", ("REACHABLE", "FRESH_HEARTBEAT")),
        (0, 0, "OFFLINE", ("UNREACHABLE", "REPORTED_OFFLINE")),
        (-15, -15, "ONLINE", ("REACHABLE", "FRESH_HEARTBEAT")),
        (-16, 0, "ONLINE", ("UNREACHABLE", "HEARTBEAT_TIMEOUT")),
        (0, -16, "ONLINE", ("UNREACHABLE", "HEARTBEAT_TIMEOUT")),
        (6, 0, "ONLINE", ("UNKNOWN", "CLOCK_SKEW")),
        (0, 6, "ONLINE", ("UNKNOWN", "CLOCK_SKEW")),
        (5, 0, "ONLINE", ("REACHABLE", "FRESH_HEARTBEAT")),
    ],
)
def test_classification(heartbeat, receipt, status, expected):
    def date(offset):
        return AT + timedelta(seconds=offset) if offset is not None else None
    assert (
        classify(
            {
                "last_heartbeat": date(heartbeat),
                "last_received_at": date(receipt),
                "status": status,
            },
            AT,
            CONFIG,
        )
        == expected
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"heartbeat_timeout_seconds": 0},
        {"heartbeat_clock_skew_seconds": -1},
        {"supervision_interval_seconds": 0},
        {"supervision_database_timeout_seconds": 0},
        {"supervision_gap_seconds": 10},
        {"supervision_metrics_port": 65536},
    ],
)
def test_config_is_bounded(changes):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **changes)


@pytest.mark.parametrize(
    "checked,stale,effective",
    [
        (None, True, "UNKNOWN"),
        (0, False, "REACHABLE"),
        (-30, False, "REACHABLE"),
        (-31, True, "UNKNOWN"),
        (6, True, "UNKNOWN"),
    ],
)
def test_read_exposes_supervision_gaps_without_changing_reported_status(checked, stale, effective):
    node = FogNodeRead(
        fog_id="FOG_A",
        zone="A",
        status="OVERLOADED",
        cpu_percent=None,
        ram_percent=None,
        queued_tasks=None,
        active_tasks=None,
        last_heartbeat=AT,
        last_received_at=AT,
        offline_since=None,
        recovered_at=None,
        supervision_status="REACHABLE",
        supervision_reason="FRESH_HEARTBEAT",
        supervision_checked_at=AT + timedelta(seconds=checked) if checked is not None else None,
    )
    result = with_heartbeat_age(node, AT, 15)
    assert result.status == "OVERLOADED" and result.supervision_status == "REACHABLE"
    assert result.supervision_stale is stale and result.effective_supervision_status == effective
    assert result.heartbeat_received_age_seconds == 0


async def test_worker_retries_without_exposing_sql_and_marks_commits(caplog):
    operation = AsyncMock(side_effect=[OperationalError("SECRET SQL", {}, Exception("DSN")), 0])
    worker = Worker(None, CONFIG, check_fn=operation)
    assert not await worker.run_once() and worker.ready._value.get() == 0
    assert worker.last_success._value.get() == 0
    assert "SECRET" not in caplog.text and "DSN" not in caplog.text
    assert await worker.run_once() and worker.ready._value.get() == 1


async def test_worker_cancel_propagates():
    worker = Worker(None, CONFIG, check_fn=AsyncMock(side_effect=asyncio.CancelledError))
    with pytest.raises(asyncio.CancelledError):
        await worker.run_once()
