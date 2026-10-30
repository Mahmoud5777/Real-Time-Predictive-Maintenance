"""T7 - Ingestion HTTP de secours (seed, tests, rejeu).

Le chemin principal reste le consommateur MQTT : cette route existe pour que MP3 soit
testable et demontrable sans dependre du calendrier de MP1/MP2.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.api.deps import require_ingest_token
from app.services.ingest import validate_batch

router = APIRouter(tags=["ingest"])


class BatchItem(BaseModel):
    kind: str
    payload: dict


class BatchRequest(BaseModel):
    messages: list[BatchItem] = Field(min_length=1, max_length=5000)


@router.post("/ingest/batch", status_code=status.HTTP_207_MULTI_STATUS)
async def ingest_batch(
    body: BatchRequest,
    _: None = Depends(require_ingest_token),
) -> Response:
    """Valide chaque element separement : un message invalide ne doit pas annuler le batch."""
    payloads = [item.model_dump() for item in body.messages]
    _valid, report = validate_batch(payloads)
    # T5/T6 : brancher ici l insertion reelle avec ON CONFLICT (message_id) DO NOTHING,
    # puis reporter les doublons dans `report.duplicates`.
    if report.accepted == 0:
        raise HTTPException(
            status_code=422,
            detail={"code": "NO_VALID_MESSAGE", "errors": report.errors},
        )
    return Response(
        content=json.dumps(
            {
                "accepted": report.accepted,
                "duplicates": report.duplicates,
                "rejected": report.rejected,
                "errors": report.errors,
            }
        ),
        media_type="application/json",
        status_code=status.HTTP_207_MULTI_STATUS,
    )

