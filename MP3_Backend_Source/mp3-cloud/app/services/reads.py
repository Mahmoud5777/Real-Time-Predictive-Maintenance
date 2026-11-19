"""Lectures SQL bornees, filtres partages et erreurs sans details de connexion."""

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import Select, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PageParams, TimeRange
from app.schemas.common import problem
from app.schemas.reads import Page, PageMeta, ReadModel, ReadProblem

READ_RESPONSES = {
    404: {"model": ReadProblem, "description": "Ressource inconnue ou mesure absente"},
    503: {"model": ReadProblem, "description": "Lecture indisponible ; reessayer plus tard"},
}


class ReadError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


async def read_error_handler(request: Request, exc: ReadError) -> JSONResponse:
    missing = exc.status == 404
    return JSONResponse(
        status_code=exc.status,
        content=problem(
            "not-found" if missing else "read-unavailable",
            "Not Found" if missing else "Service Unavailable",
            exc.status,
            exc.detail,
            request.url.path,
        ),
    )


def filter_time(query: Select, column, window: TimeRange) -> Select:
    if window.from_ is not None:
        query = query.where(column >= window.from_)
    if window.to is not None:
        query = query.where(column <= window.to)
    return query


def ordered(query: Select, sort: str, columns: dict, identity) -> Select:
    # Les noms proviennent des Literal de la route, jamais d'un fragment SQL client.
    column = columns[sort.removeprefix("-")]
    descending = sort.startswith("-")
    primary = column.desc() if descending else column.asc()
    tie = identity.desc() if descending else identity.asc()
    return query.order_by(primary.nulls_last(), tie)


async def read_page[T: ReadModel](
    session: AsyncSession, query: Select, page: PageParams, model: type[T]
) -> Page[T]:
    try:
        count = select(func.count()).select_from(query.order_by(None).subquery())
        total = (await session.execute(count)).scalar_one()
        rows = (await session.execute(query.limit(page.limit).offset(page.offset))).scalars().all()
    except (SQLAlchemyError, OSError, TimeoutError) as exc:
        raise ReadError(503, "Stored observations cannot be read at this time") from exc
    return Page[model](
        items=[model.model_validate(row) for row in rows],
        meta=PageMeta(limit=page.limit, offset=page.offset, total=total),
    )


async def read_one[T: ReadModel](
    session: AsyncSession, query: Select, model: type[T], detail: str
) -> T:
    try:
        row = (await session.execute(query)).scalar_one_or_none()
    except (SQLAlchemyError, OSError, TimeoutError) as exc:
        raise ReadError(503, "Stored observations cannot be read at this time") from exc
    if row is None:
        raise ReadError(404, detail)
    return model.model_validate(row)
