"""T8 - Catalogue et derniere mesure, avec identite stable en cas de dates egales."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PageParams
from app.db.session import get_session
from app.models.tables import Machine, SensorData
from app.schemas.messages import Zone
from app.schemas.reads import MachineRead, MachineSort, MeasurementRead, Page
from app.services.reads import READ_RESPONSES, ordered, read_one, read_page

router = APIRouter(responses=READ_RESPONSES)


@router.get("/machines", tags=["machines"], response_model=Page[MachineRead])
async def list_machines(
    zone: Zone | None = None,
    sort: MachineSort = "machine_id",
    page: PageParams = Depends(),
    session: AsyncSession = Depends(get_session),
) -> Page[MachineRead]:
    query = select(Machine)
    if zone is not None:
        query = query.where(Machine.zone == zone)
    query = ordered(
        query,
        sort,
        {
            "machine_id": Machine.machine_id,
            "name": Machine.name,
            "zone": Machine.zone,
        },
        Machine.machine_id,
    )
    return await read_page(session, query, page, MachineRead)


@router.get("/machines/{machine_id}", tags=["machines"], response_model=MachineRead)
async def get_machine(machine_id: str, session: AsyncSession = Depends(get_session)) -> MachineRead:
    return await read_one(
        session,
        select(Machine).where(Machine.machine_id == machine_id),
        MachineRead,
        f"Unknown machine {machine_id}",
    )


@router.get("/machines/{machine_id}/latest", tags=["measurements"], response_model=MeasurementRead)
async def latest_measurement(
    machine_id: str, session: AsyncSession = Depends(get_session)
) -> MeasurementRead:
    await get_machine(machine_id, session)
    query = select(SensorData).where(SensorData.machine_id == machine_id)
    query = query.order_by(SensorData.timestamp.desc(), SensorData.id.desc()).limit(1)
    return await read_one(
        session, query, MeasurementRead, f"No measurement stored yet for {machine_id}"
    )
