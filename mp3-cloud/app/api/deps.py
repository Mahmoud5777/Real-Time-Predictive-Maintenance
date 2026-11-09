"""Dependances transverses : authentification d ingestion et parametres de requete."""

import secrets

from fastapi import Header, HTTPException, Query, status
from fastapi.exceptions import RequestValidationError

from app.config import get_settings
from app.schemas.common import UtcDatetime


async def require_ingest_token(authorization: str | None = Header(default=None)) -> None:
    """Protege les routes d ecriture.

    Le dashboard (lecture) n a pas besoin de token ; l ingestion oui, sinon n importe qui
    peut corrompre l historique et donc tous les KPI.
    """
    expected = get_settings().ingest_token
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not expected or not secrets.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"type": "unauthorized", "title": "Invalid or missing bearer token"},
        )


class PageParams:
    """Pagination bornee ; chaque route declare ses champs de tri autorises."""

    def __init__(
        self,
        limit: int = Query(default=50, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
    ) -> None:
        self.limit = limit
        self.offset = offset


class TimeRange:
    """Bornes inclusives normalisees en UTC ; aucune date locale naive."""

    def __init__(
        self,
        from_: UtcDatetime | None = Query(default=None, alias="from"),
        to: UtcDatetime | None = Query(default=None),
    ) -> None:
        if from_ is not None and to is not None and from_ > to:
            raise RequestValidationError(
                [
                    {
                        "type": "value_error",
                        "loc": ("query", "to"),
                        "msg": "to must be greater than or equal to from",
                        "input": to.isoformat(),
                    }
                ]
            )
        self.from_ = from_
        self.to = to
