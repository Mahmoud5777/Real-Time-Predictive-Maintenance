"""Dependances transverses : authentification d ingestion et parametres de requete."""

import secrets

from fastapi import Header, HTTPException, Query, status

from app.config import get_settings


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
    """Pagination et tri normalises pour toutes les listes."""

    def __init__(
        self,
        limit: int = Query(default=50, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
        sort: str = Query(default="-timestamp", description="'-' prefixe = descendant"),
    ) -> None:
        self.limit = limit
        self.offset = offset
        self.descending = sort.startswith("-")
        self.sort_field = sort.lstrip("-")
