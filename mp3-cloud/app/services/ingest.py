"""T5/T6/T7 - Pipeline d ingestion commun au MQTT et au HTTP batch.

Un seul chemin d ecriture pour les deux transports : c est ce qui garantit que la
deduplication et la validation s appliquent partout de la meme facon.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import (
    Alert,
    FogNode,
    FogStatusHistory,
    Prediction,
    SensorData,
    Task,
)
from app.models.tables import TaskEvent as StoredTaskEvent
from app.schemas.messages import (
    AlertMessage,
    FogStatus,
    MachineData,
    PredictionResult,
    TaskEvent,
)

SCHEMA_BY_KIND: dict[str, type] = {
    "sensor": MachineData,
    "prediction": PredictionResult,
    "alert": AlertMessage,
    "fog_status": FogStatus,
    "task_event": TaskEvent,
}

MODEL_BY_KIND = {
    "sensor": SensorData,
    "prediction": Prediction,
    "alert": Alert,
    "fog_status": FogStatusHistory,
    "task_event": StoredTaskEvent,
}


class MessageConflict(Exception):
    """Erreur metier isolee au message, sans exposer les details SQL."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass
class IngestReport:
    accepted: int = 0
    duplicates: int = 0
    rejected: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.accepted + self.duplicates + self.rejected


def parse_message(kind: str, payload: dict[str, Any]) -> Any:
    """Valide un message ; leve ValidationError si le contrat n est pas respecté."""
    schema = SCHEMA_BY_KIND.get(kind)
    if schema is None:
        raise ValueError(f"unknown message kind: {kind}")
    return schema.model_validate(payload)


def validate_batch(messages: list[dict[str, Any]]) -> tuple[list[Any], IngestReport]:
    """Etape pure (sans base) de la validation d un batch HTTP -> testable unitairement."""
    report = IngestReport()
    valid: list[Any] = []
    for index, item in enumerate(messages):
        kind, payload = item.get("kind"), item.get("payload") or {}
        try:
            valid.append(parse_message(kind, payload))
            report.accepted += 1
        except ValidationError as exc:
            report.rejected += 1
            report.errors.append(
                {"index": index, "code": "VALIDATION_ERROR", "detail": exc.errors()[0]["msg"]}
            )
        except ValueError as exc:
            report.rejected += 1
            report.errors.append({"index": index, "code": "UNKNOWN_KIND", "detail": str(exc)})
    return valid, report


async def _insert_message(
    session: AsyncSession, model: type, values: dict[str, Any], received_at: datetime
) -> bool:
    """L'unicite arbitre les envois concurrents ; un conflit de contenu est rejete."""
    statement = (
        insert(model)
        .values(**values, received_at=received_at)
        .on_conflict_do_nothing(index_elements=["message_id"])
        .returning(model.id)
    )
    if (await session.execute(statement)).scalar_one_or_none() is not None:
        return True
    previous = (
        await session.execute(
            select(model.__table__).where(model.message_id == values["message_id"])
        )
    ).mappings().one()
    if any(previous[key] != value for key, value in values.items()):
        raise MessageConflict(
            "MESSAGE_ID_CONFLICT", "message_id already exists with different content"
        )
    return False


async def _write_fog(session: AsyncSession, message: FogStatus) -> bool:
    # Verrouiller avant l'historique : charge courante et observation restent atomiques.
    node = (
        await session.execute(
            select(FogNode.__table__)
            .where(FogNode.fog_id == message.fog_id)
            .with_for_update()
        )
    ).mappings().one_or_none()
    if node is None or node["zone"] != message.zone:
        raise MessageConflict("REFERENCE_ERROR", "Fog is missing or does not belong to this zone")
    values = message.model_dump()
    values["observed_at"] = values.pop("last_heartbeat")
    received_at = datetime.now(UTC)
    if not await _insert_message(session, FogStatusHistory, values, received_at):
        return False
    # A date egale, la premiere observation enregistree reste courante.
    heartbeat = node["last_heartbeat"]
    if heartbeat is None or message.last_heartbeat > heartbeat:
        current = message.model_dump(exclude={"message_id", "fog_id", "zone"})
        current["last_received_at"] = received_at
        if message.status == "OFFLINE":
            if node["status"] != "OFFLINE" or node["offline_since"] is None:
                current["offline_since"] = message.last_heartbeat
        else:
            current["offline_since"] = None
            # L'etat OFFLINE du catalogue n'est pas une panne observee.
            if node["status"] == "OFFLINE" and heartbeat is not None:
                current["recovered_at"] = message.last_heartbeat
        await session.execute(
            update(FogNode).where(FogNode.fog_id == message.fog_id).values(**current)
        )
    return True


def _task_assignment(message: TaskEvent) -> str | None:
    if message.status in {"MIGRATED", "RECOVERED"}:
        return message.destination_fog
    return message.source_fog


async def _write_task(session: AsyncSession, message: TaskEvent) -> bool:
    values = message.model_dump()
    values["task_id"] = values["task_id"].lower()
    origin = message.source_fog if message.status == "CREATED" else None
    # Le parent doit exister avant l'evenement. Le savepoint annule un parent orphelin
    # si le message s'avere ensuite invalide ou reutilise un identifiant different.
    await session.execute(
        insert(Task)
        .values(
            task_id=values["task_id"],
            task_type=message.task_type,
            priority=message.priority,
            critical=message.critical,
            origin_fog_id=origin,
            current_fog_id=_task_assignment(message),
            status=message.status,
            created_at=message.created_at,
        )
        .on_conflict_do_nothing(index_elements=["task_id"])
    )
    task = (
        await session.execute(
            select(Task.__table__).where(Task.task_id == values["task_id"]).with_for_update()
        )
    ).mappings().one()
    if task["task_type"] != message.task_type or task["created_at"] != message.created_at:
        raise MessageConflict("TASK_CONFLICT", "task type and creation date must remain stable")
    if origin is not None and task["origin_fog_id"] not in {None, origin}:
        raise MessageConflict("TASK_CONFLICT", "known task origin cannot be changed")
    received_at = datetime.now(UTC)
    if not await _insert_message(session, StoredTaskEvent, values, received_at):
        return False
    current: dict[str, Any] = {"last_received_at": received_at}
    if origin is not None and task["origin_fog_id"] is None:
        current["origin_fog_id"] = origin
    # Une creation tardive complete l'origine sans effacer une migration observee.
    # COMPLETED reste terminal pour ce task_id (aucune tentative dans le contrat).
    late_creation = message.status == "CREATED" and task["status"] != "CREATED"
    if not late_creation and task["status"] != "COMPLETED":
        current.update(
            status=message.status,
            current_fog_id=_task_assignment(message),
            priority=message.priority,
            critical=message.critical,
        )
    if message.status == "COMPLETED" and message.completed_at is not None:
        if task["completed_at"] not in {None, message.completed_at}:
            raise MessageConflict("TASK_CONFLICT", "known task completion date cannot be changed")
        current["completed_at"] = message.completed_at
    # Ni started_at ni last_event_at ne peuvent etre deduits de l'heure de reception.
    await session.execute(update(Task).where(Task.task_id == values["task_id"]).values(**current))
    return True


async def _write_message(session: AsyncSession, kind: str, message: Any) -> bool:
    if kind == "fog_status":
        return await _write_fog(session, message)
    if kind == "task_event":
        return await _write_task(session, message)
    return await _insert_message(
        session, MODEL_BY_KIND[kind], message.model_dump(), datetime.now(UTC)
    )


def _integrity_problem(exc: IntegrityError) -> MessageConflict | None:
    sqlstate = getattr(exc.orig, "sqlstate", None)
    if sqlstate == "23503":
        return MessageConflict("REFERENCE_ERROR", "unknown or inconsistent catalogue reference")
    if sqlstate == "23505":
        return MessageConflict("IDENTIFIER_CONFLICT", "a business identifier already exists")
    if sqlstate in {"23514", "23502", "22001"}:
        return MessageConflict("DATA_INTEGRITY_ERROR", "data violates a database constraint")
    return None


async def persist_batch(session: AsyncSession, messages: list[dict[str, Any]]) -> IngestReport:
    """Transaction de lot, savepoint par element ; retour seulement apres commit.

    Une panne de base remonte a l'appelant et annule le lot entier. Le service possede
    sa transaction : lui fournir une session sans transaction deja ouverte.
    """
    report = IngestReport()
    async with session.begin():
        for index, item in enumerate(messages):
            try:
                try:
                    message = parse_message(item.get("kind"), item.get("payload"))
                except ValueError as exc:
                    if isinstance(exc, ValidationError):
                        raise
                    raise MessageConflict("UNKNOWN_KIND", str(exc)) from exc
                async with session.begin_nested():
                    inserted = await _write_message(session, item["kind"], message)
                if inserted:
                    report.accepted += 1
                else:
                    report.duplicates += 1
            except ValidationError as exc:
                report.rejected += 1
                report.errors.append(
                    {"index": index, "code": "VALIDATION_ERROR", "detail": exc.errors()[0]["msg"]}
                )
            except MessageConflict as exc:
                report.rejected += 1
                report.errors.append({"index": index, "code": exc.code, "detail": exc.detail})
            except IntegrityError as exc:
                problem = _integrity_problem(exc)
                if problem is None:
                    raise
                report.rejected += 1
                report.errors.append(
                    {"index": index, "code": problem.code, "detail": problem.detail}
                )
    return report
