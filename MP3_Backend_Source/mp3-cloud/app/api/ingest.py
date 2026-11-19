"""T7 - Ingestion HTTP de secours (seed, tests, rejeu).

Le chemin principal reste le consommateur MQTT : cette route existe pour que MP3 soit
testable et demontrable sans dependre du calendrier de MP1/MP2.
"""

from dataclasses import asdict

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import DBAPIError
from sqlalchemy.exc import TimeoutError as DatabaseTimeout
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_ingest_token
from app.db.session import get_session
from app.schemas.common import problem
from app.services.ingest import persist_batch

router = APIRouter(tags=["ingest"])


class BatchItem(BaseModel):
    kind: str
    payload: dict


class BatchRequest(BaseModel):
    messages: list[BatchItem] = Field(min_length=1, max_length=5000)


class ItemError(BaseModel):
    index: int
    code: str
    detail: str


class BatchReport(BaseModel):
    accepted: int
    duplicates: int
    rejected: int
    errors: list[ItemError]


@router.post(
    "/ingest/batch",
    status_code=status.HTTP_207_MULTI_STATUS,
    response_model=BatchReport,
    responses={
        401: {"description": "Bearer token absent ou invalide"},
        422: {"description": "Enveloppe invalide ou tous les messages rejetes"},
        503: {"description": "Transaction impossible ; aucun resultat d'ingestion confirme"},
    },
)
async def ingest_batch(
    body: BatchRequest,
    request: Request,
    _: None = Depends(require_ingest_token),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    """Enregistre chaque message valide ; un doublon seul reste un succes de rejeu."""
    payloads = [item.model_dump() for item in body.messages]
    try:
        report = await persist_batch(session, payloads)
    except (DBAPIError, DatabaseTimeout, OSError, TimeoutError):
        return JSONResponse(
            status_code=503,
            content=problem(
                "database-unavailable",
                "Database unavailable",
                503,
                "The batch transaction could not be confirmed; retry the same message IDs",
                request.url.path,
            ),
        )
    result = asdict(report)
    if report.accepted + report.duplicates == 0:
        return JSONResponse(
            status_code=422,
            content={
                **problem(
                    "no-valid-message",
                    "No valid message",
                    422,
                    "All messages were rejected",
                    request.url.path,
                ),
                "code": "NO_VALID_MESSAGE",
                **result,
            },
        )
    return JSONResponse(content=result, status_code=status.HTTP_207_MULTI_STATUS)

