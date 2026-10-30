"""T5/T6/T7 - Pipeline d ingestion commun au MQTT et au HTTP batch.

Un seul chemin d ecriture pour les deux transports : c est ce qui garantit que la
deduplication et la validation s appliquent partout de la meme facon.
"""

from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

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
