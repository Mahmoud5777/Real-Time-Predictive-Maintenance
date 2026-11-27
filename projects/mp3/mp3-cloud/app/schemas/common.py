from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, WrapValidator, field_validator

_UTC = UTC


def _require_utc_timestamp(value: object) -> datetime:
    """Convertit et verifie un timestamp : l heure locale naive est refusee.

    Trois conteneurs = trois fuseaux differents possibles. Sans UTC explicite, chaque
    KPI calcule par le Cloud devient faux. Une chaine sans suffixe (`2026-10-30T14:25:31`)
    est donc invalide volontairement : le producteur doit horodater en UTC.
    """
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("timestamp must not be empty")
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"timestamp is not ISO-8601: {value}") from exc
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise ValueError("timestamp must be a datetime or an ISO-8601 string")

    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware (UTC: 'Z' or '+00:00')")
    return parsed.astimezone(_UTC)


def _utc_validator(value: object, handler) -> datetime:
    """Point d entree Pydantic : normalise d abord, puis laisse le controle habituel faire."""
    return handler(_require_utc_timestamp(value))


UtcDatetime = Annotated[datetime, WrapValidator(_utc_validator)]


class MessageBase(BaseModel):
    """Tout message publie porte un `message_id` unique : c est la cle de deduplication."""

    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(min_length=8, max_length=64)

    @field_validator("message_id")
    @classmethod
    def _must_be_printable(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 8:
            raise ValueError("message_id must be a non-empty unique identifier")
        return cleaned


def problem(type_uri: str, title: str, status: int, detail: str, instance: str) -> dict:
    """Corps d erreur normalise RFC 7807 : le client recoit toujours la meme forme."""
    return {
        "type": f"https://fog-project/errors/{type_uri}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": instance,
    }


