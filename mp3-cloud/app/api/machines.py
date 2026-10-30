"""T8 - Lecture des machines et des mesures."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PageParams
from app.db.session import get_session
from app.models.tables import Machine, SensorData

router = APIRouter(tags=["machines", "measurements"])


@router.get("/machines")
async def list_machines(
    zone: str | None = None,
    page: PageParams = Depends(),
    session: AsyncSession = Depends(get_session),
) -> dict:
    query = select(Machine)
    count = select(func.count()).select_from(Machine)
    if zone:
        query = query.where(Machine.zone == zone)
        count = count.where(Machine.zone == zone)

    total = (await session.execute(count)).scalar_one()
    paged = query.order_by(Machine.machine_id).limit(page.limit).offset(page.offset)
    rows = (await session.execute(paged)).scalars().all()
    return {
        "items": [
            {
                "machine_id": m.machine_id,
                "name": m.name,
                "machine_type": m.machine_type,
                "zone": m.zone,
                "fog_id": m.fog_id,
            }
            for m in rows
        ],
        "meta": {"limit": page.limit, "offset": page.offset, "total": total},
    }


@router.get("/machines/{machine_id}")
async def get_machine(machine_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    machine = await session.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown machine {machine_id}",
        )
    return {
        "machine_id": machine.machine_id,
        "name": machine.name,
        "machine_type": machine.machine_type,
        "zone": machine.zone,
        "fog_id": machine.fog_id,
    }


@router.get("/machines/{machine_id}/latest")
async def latest_measurement(
    machine_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = (
        await session.execute(
            select(SensorData)
            .where(SensorData.machine_id == machine_id)
            .order_by(SensorData.timestamp.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no measurement stored yet for {machine_id}",
        )
    return {
        "machine_id": row.machine_id,
        "zone": row.zone,
        "timestamp": row.timestamp.isoformat(),
        "temperature": row.temperature,
        "vibration": row.vibration,
        "speed": row.speed,
        "current": row.current,
        "state": row.state,
    }


