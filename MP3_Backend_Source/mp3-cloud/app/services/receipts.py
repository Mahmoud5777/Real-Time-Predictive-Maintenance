"""Semantic SHA-256 identity of validated messages, independent of transport JSON formatting."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from app.models.tables import IngestReceipt, KpiRecord, Prediction, SensorData
from app.schemas.messages import MachineData, PredictionResult

RETENTION_LOCK = 6030008
FINALIZED_METRIC = "_retention_finalized"
SCHEMAS = {"sensor": MachineData, "prediction": PredictionResult}


def canonical(value):
    if value is None or isinstance(value, bool | str):
        return value
    if isinstance(value, datetime):
        return {"utc": value.astimezone(UTC).isoformat(timespec="microseconds")}
    if isinstance(value, int | float | Decimal):
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError("Receipt numbers must be finite")
        sign, digits, exponent = number.as_tuple()
        significant = "".join(str(digit) for digit in digits)
        trimmed = significant.rstrip("0")
        if not trimmed:
            return {"number": "0"}
        return {"number": f"{sign}:{trimmed}:{exponent+len(significant)-len(trimmed)}"}
    if isinstance(value, dict):
        return {key: canonical(item) for key, item in value.items()}
    raise TypeError("Unsupported receipt value")


def digest(kind, payload):
    message = SCHEMAS[kind].model_validate(payload)
    body = json.dumps(
        canonical(message.model_dump()), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(body.encode("utf-8")).digest()


def stored_payload(kind, row):
    # Lifecycle fields are not producer input and must not alter original message identity.
    return {name: row[name] for name in SCHEMAS[kind].model_fields}


async def reserve_receipt(session, kind, message):
    payload = message.model_dump()
    fingerprint = digest(kind, payload)
    created = (
        await session.execute(
            insert(IngestReceipt)
            .values(
                kind=kind,
                message_id=message.message_id,
                payload_sha256=fingerprint,
            )
            .on_conflict_do_nothing(index_elements=["kind", "message_id"])
            .returning(IngestReceipt.message_id)
        )
    ).scalar_one_or_none()
    if created is None:
        previous = await session.scalar(
            select(IngestReceipt.payload_sha256).where(
                IngestReceipt.kind == kind,
                IngestReceipt.message_id == message.message_id,
            )
        )
        return "duplicate" if previous == fingerprint else "conflict"
    hour = message.timestamp.replace(minute=0, second=0, microsecond=0)
    sealed = await session.scalar(
        select(KpiRecord.id).where(
            KpiRecord.metric == FINALIZED_METRIC,
            KpiRecord.scope == "plant",
            KpiRecord.scope_value == "all",
            KpiRecord.bucket_start == hour,
        )
    )
    if sealed is not None:
        # A legacy latest measurement may still be retained without a receipt backfill.
        model = SensorData if kind == "sensor" else Prediction
        previous = (
            (
                await session.execute(
                    select(model.__table__).where(model.message_id == message.message_id)
                )
            )
            .mappings()
            .one_or_none()
        )
        if previous is not None:
            return (
                "duplicate"
                if digest(kind, stored_payload(kind, previous)) == fingerprint
                else "conflict"
            )
        return "expired"
    return "new"


async def ingest_retention_barrier(session):
    # Multiple ingress transactions can proceed together; finalization excludes all app writers.
    await session.execute(
        text("SELECT pg_advisory_xact_lock_shared(:lock)"), {"lock": RETENTION_LOCK}
    )
