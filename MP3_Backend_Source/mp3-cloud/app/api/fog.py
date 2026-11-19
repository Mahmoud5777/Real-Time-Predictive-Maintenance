"""Etat rapporte et historique des Fog ; une lecture ne modifie pas la supervision."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PageParams, TimeRange
from app.config import get_settings
from app.db.session import get_session
from app.models.tables import FogNode, FogStatusHistory
from app.schemas.messages import FogId, Zone
from app.schemas.reads import (
    FogHistoryRead,
    FogNodePage,
    FogNodeRead,
    FogSupervisionRead,
    HistorySort,
    NodeSort,
    NodeStatus,
    Page,
    SupervisionStatus,
)
from app.services.reads import READ_RESPONSES, filter_time, ordered, read_one, read_page

router = APIRouter(tags=["fog"], responses=READ_RESPONSES)


def with_heartbeat_age(node: FogNodeRead, as_of: datetime, timeout: int) -> FogNodeRead:
    stale = (
        node.supervision_checked_at is None
        or (as_of - node.supervision_checked_at).total_seconds()
        > get_settings().supervision_gap_seconds
        or (as_of - node.supervision_checked_at).total_seconds()
        < -get_settings().heartbeat_clock_skew_seconds
    )
    age = (as_of - node.last_heartbeat).total_seconds() if node.last_heartbeat is not None else None
    return node.model_copy(
        update={
            "heartbeat_age_seconds": age,
            "heartbeat_stale": age > timeout if age is not None else None,
            "heartbeat_received_age_seconds": (as_of - node.last_received_at).total_seconds()
            if node.last_received_at is not None
            else None,
            "supervision_stale": stale,
            "effective_supervision_status": "UNKNOWN" if stale else node.supervision_status,
        }
    )


@router.get("/fog/nodes", response_model=FogNodePage)
async def fog_nodes(
    zone: Zone | None = None,
    status: NodeStatus | None = None,
    supervision_status: SupervisionStatus | None = None,
    sort: NodeSort = "fog_id",
    page: PageParams = Depends(),
    session: AsyncSession = Depends(get_session),
) -> FogNodePage:
    query = select(FogNode)
    if zone is not None:
        query = query.where(FogNode.zone == zone)
    if status is not None:
        query = query.where(FogNode.status == status)
    if supervision_status is not None:
        query = query.where(FogNode.supervision_status == supervision_status)
    query = ordered(
        query,
        sort,
        {
            "fog_id": FogNode.fog_id,
            "zone": FogNode.zone,
            "last_heartbeat": FogNode.last_heartbeat,
        },
        FogNode.fog_id,
    )
    result = await read_page(session, query, page, FogNodeRead)
    as_of = datetime.now(UTC)
    timeout = get_settings().heartbeat_timeout_seconds
    return FogNodePage(
        items=[with_heartbeat_age(node, as_of, timeout) for node in result.items],
        meta=result.meta,
        as_of=as_of,
        heartbeat_timeout_seconds=timeout,
        supervision_gap_seconds=get_settings().supervision_gap_seconds,
    )


@router.get("/fog/nodes/{fog_id}", response_model=FogNodeRead)
async def fog_detail(fog_id: FogId, session: AsyncSession = Depends(get_session)) -> FogNodeRead:
    result = await read_one(
        session,
        select(FogNode).where(FogNode.fog_id == fog_id),
        FogNodeRead,
        f"Unknown Fog node {fog_id}",
    )
    return with_heartbeat_age(result, datetime.now(UTC), get_settings().heartbeat_timeout_seconds)


@router.get("/fog/status-history", response_model=Page[FogHistoryRead])
async def fog_history(
    fog_id: FogId | None = None,
    zone: Zone | None = None,
    status: NodeStatus | None = None,
    sort: HistorySort = "-observed_at",
    window: TimeRange = Depends(),
    page: PageParams = Depends(),
    session: AsyncSession = Depends(get_session),
) -> Page[FogHistoryRead]:
    query = select(FogStatusHistory).where(FogStatusHistory.record_type == "HEARTBEAT")
    for column, value in (
        (FogStatusHistory.fog_id, fog_id),
        (FogStatusHistory.zone, zone),
        (FogStatusHistory.status, status),
    ):
        if value is not None:
            query = query.where(column == value)
    query = filter_time(query, FogStatusHistory.observed_at, window)
    query = ordered(
        query,
        sort,
        {
            "observed_at": FogStatusHistory.observed_at,
            "received_at": FogStatusHistory.received_at,
            "id": FogStatusHistory.id,
        },
        FogStatusHistory.id,
    )
    return await read_page(session, query, page, FogHistoryRead)


@router.get("/fog/supervision-history", response_model=Page[FogSupervisionRead])
async def supervision_history(
    fog_id: FogId | None = None,
    zone: Zone | None = None,
    supervision_status: SupervisionStatus | None = None,
    sort: HistorySort = "-observed_at",
    window: TimeRange = Depends(),
    page: PageParams = Depends(),
    session: AsyncSession = Depends(get_session),
) -> Page[FogSupervisionRead]:
    query = select(FogStatusHistory).where(FogStatusHistory.record_type == "SUPERVISION")
    for column, value in [
        (FogStatusHistory.fog_id, fog_id),
        (FogStatusHistory.zone, zone),
        (FogStatusHistory.supervision_status, supervision_status),
    ]:
        if value is not None:
            query = query.where(column == value)
    query = filter_time(query, FogStatusHistory.observed_at, window)
    query = ordered(
        query,
        sort,
        {
            "observed_at": FogStatusHistory.observed_at,
            "received_at": FogStatusHistory.received_at,
            "id": FogStatusHistory.id,
        },
        FogStatusHistory.id,
    )
    return await read_page(session, query, page, FogSupervisionRead)
