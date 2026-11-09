"""Historique des mesures, predictions et alertes pour MP4."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PageParams, TimeRange
from app.db.session import get_session
from app.models.tables import Alert, Machine, Prediction, SensorData
from app.schemas.messages import FogId, Zone
from app.schemas.reads import (
    AlertRead,
    AlertStatus,
    MachineId,
    MeasurementRead,
    MeasurementSort,
    Page,
    PredictionRead,
    PredictionSort,
    Severity,
)
from app.services.reads import READ_RESPONSES, filter_time, ordered, read_one, read_page

router = APIRouter(responses=READ_RESPONSES)


@router.get("/measurements", tags=["measurements"], response_model=Page[MeasurementRead])
async def measurements(
    machine_id: MachineId | None = None,
    zone: Zone | None = None,
    sort: MeasurementSort = "-timestamp",
    window: TimeRange = Depends(),
    page: PageParams = Depends(),
    session: AsyncSession = Depends(get_session),
) -> Page[MeasurementRead]:
    query = select(SensorData)
    if machine_id is not None:
        query = query.where(SensorData.machine_id == machine_id)
    if zone is not None:
        query = query.where(SensorData.zone == zone)
    query = filter_time(query, SensorData.timestamp, window)
    query = ordered(
        query,
        sort,
        {
            "timestamp": SensorData.timestamp,
            "received_at": SensorData.received_at,
            "id": SensorData.id,
        },
        SensorData.id,
    )
    return await read_page(session, query, page, MeasurementRead)


@router.get("/predictions", tags=["predictions"], response_model=Page[PredictionRead])
async def predictions(
    machine_id: MachineId | None = None,
    zone: Zone | None = None,
    fog_id: FogId | None = None,
    anomaly: bool | None = None,
    severity: Severity | None = None,
    model_version: str | None = Query(default=None, min_length=1, max_length=64),
    sort: PredictionSort = "-timestamp",
    window: TimeRange = Depends(),
    page: PageParams = Depends(),
    session: AsyncSession = Depends(get_session),
) -> Page[PredictionRead]:
    query = select(Prediction).join(Machine, Prediction.machine_id == Machine.machine_id)
    for column, value in (
        (Prediction.machine_id, machine_id),
        (Machine.zone, zone),
        (Prediction.fog_id, fog_id),
        (Prediction.anomaly, anomaly),
        (Prediction.severity, severity),
        (Prediction.model_version, model_version),
    ):
        if value is not None:
            query = query.where(column == value)
    query = filter_time(query, Prediction.timestamp, window)
    query = ordered(
        query,
        sort,
        {
            "timestamp": Prediction.timestamp,
            "received_at": Prediction.received_at,
            "risk_score": Prediction.risk_score,
            "id": Prediction.id,
        },
        Prediction.id,
    )
    return await read_page(session, query, page, PredictionRead)


@router.get("/alerts", tags=["alerts"], response_model=Page[AlertRead])
async def alerts(
    machine_id: MachineId | None = None,
    zone: Zone | None = None,
    fog_id: FogId | None = None,
    status: AlertStatus | None = None,
    severity: Severity | None = None,
    sort: MeasurementSort = "-timestamp",
    window: TimeRange = Depends(),
    page: PageParams = Depends(),
    session: AsyncSession = Depends(get_session),
) -> Page[AlertRead]:
    query = select(Alert).join(Machine, Alert.machine_id == Machine.machine_id)
    for column, value in (
        (Alert.machine_id, machine_id),
        (Machine.zone, zone),
        (Alert.fog_id, fog_id),
        (Alert.status, status),
        (Alert.severity, severity),
    ):
        if value is not None:
            query = query.where(column == value)
    query = filter_time(query, Alert.timestamp, window)
    query = ordered(
        query,
        sort,
        {
            "timestamp": Alert.timestamp,
            "received_at": Alert.received_at,
            "id": Alert.id,
        },
        Alert.id,
    )
    return await read_page(session, query, page, AlertRead)


@router.get("/alerts/{alert_id}", tags=["alerts"], response_model=AlertRead)
async def alert_detail(alert_id: str, session: AsyncSession = Depends(get_session)) -> AlertRead:
    return await read_one(
        session,
        select(Alert).where(Alert.alert_id == alert_id),
        AlertRead,
        f"Unknown alert {alert_id}",
    )
