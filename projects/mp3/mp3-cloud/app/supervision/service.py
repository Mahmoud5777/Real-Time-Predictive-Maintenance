"""Atomic state transitions serialized with heartbeat ingestion by Fog row locks."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import insert, select, text, update

from app.models.tables import FogNode, FogStatusHistory


def classify(node, now, config):
    heartbeat, receipt = node["last_heartbeat"], node["last_received_at"]
    if heartbeat is None or receipt is None:
        return "UNKNOWN", "NO_HEARTBEAT"
    tolerance = timedelta(seconds=config.heartbeat_clock_skew_seconds)
    if heartbeat > now + tolerance or receipt > now + tolerance:
        return "UNKNOWN", "CLOCK_SKEW"
    timeout = timedelta(seconds=config.heartbeat_timeout_seconds)
    # A recently delivered retained/delayed old heartbeat is not fresh evidence.
    if now - heartbeat > timeout or now - receipt > timeout:
        return "UNREACHABLE", "HEARTBEAT_TIMEOUT"
    if node["status"] == "OFFLINE":
        return "UNREACHABLE", "REPORTED_OFFLINE"
    return "REACHABLE", "FRESH_HEARTBEAT"


async def transition(session, node, status, reason, now, config, *, gap_start=None):
    await session.execute(
        insert(FogStatusHistory).values(
            message_id=f"cloud-supervision-{uuid4().hex}",
            fog_id=node["fog_id"],
            zone=node["zone"],
            observed_at=now,
            received_at=now,
            record_type="SUPERVISION",
            status=None,
            cpu_percent=None,
            ram_percent=None,
            queued_tasks=None,
            active_tasks=None,
            supervision_status=status,
            previous_supervision_status=node["supervision_status"],
            supervision_reason=reason,
            evidence_heartbeat_at=node["last_heartbeat"],
            evidence_received_at=node["last_received_at"],
            timeout_seconds=config.heartbeat_timeout_seconds,
            gap_start=gap_start,
            gap_end=now if gap_start is not None else None,
        )
    )
    node.update(supervision_status=status, supervision_reason=reason, supervision_since=now)


async def check_nodes(factory, config, *, now=None):
    """One bounded transaction. Dates mean Cloud decision time, never actual failure time."""
    if now is not None and (now.tzinfo is None or now.utcoffset() is None):
        raise ValueError("Timezone-aware supervision time is required")
    async with asyncio.timeout(config.supervision_database_timeout_seconds):
        async with factory() as session, session.begin():
            await session.execute(
                text("SELECT set_config('statement_timeout', :timeout, true)"),
                {"timeout": str(int(config.supervision_database_timeout_seconds * 1000))},
            )
            rows = (
                (
                    await session.execute(
                        # key_share=True sans read=True = PostgreSQL FOR NO KEY UPDATE.
                        # Meme verrou que les heartbeats ; les FK ne changent pas l'etat.
                        select(FogNode.__table__)
                        .order_by(FogNode.fog_id)
                        .with_for_update(key_share=True)
                    )
                )
                .mappings()
                .all()
            )
            if {row["fog_id"] for row in rows} != {"FOG_A", "FOG_B", "FOG_C"}:
                raise ValueError("Fog catalogue is not initialized")
            # Capture decision time after locks: a concurrent fresh heartbeat must not look future.
            checked_at = (now or datetime.now(UTC)).astimezone(UTC)
            written = 0
            for row in rows:
                node = dict(row)
                previous_check = node["supervision_checked_at"]
                if previous_check is not None and checked_at <= previous_check:
                    continue  # Clock rollback/replay must not create backwards history.
                if (
                    previous_check is not None
                    and node["last_heartbeat"] is not None
                    and (checked_at - previous_check).total_seconds()
                    > config.supervision_gap_seconds
                ):
                    await transition(
                        session,
                        node,
                        "UNKNOWN",
                        "MONITOR_GAP",
                        checked_at,
                        config,
                        gap_start=previous_check,
                    )
                    written += 1
                status, reason = classify(node, checked_at, config)
                if (status, reason) != (node["supervision_status"], node["supervision_reason"]):
                    await transition(session, node, status, reason, checked_at, config)
                    written += 1
                await session.execute(
                    update(FogNode)
                    .where(FogNode.fog_id == node["fog_id"])
                    .values(
                        supervision_status=node["supervision_status"],
                        supervision_reason=node["supervision_reason"],
                        supervision_since=node["supervision_since"],
                        supervision_checked_at=checked_at,
                    )
                )
    return written
