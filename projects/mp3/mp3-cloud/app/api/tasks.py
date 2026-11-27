"""Projection des taches et journal ; les dates d'evenement inconnues ne sont pas inventees."""

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PageParams, TimeRange
from app.db.session import get_session
from app.models.tables import Task, TaskEvent
from app.schemas.messages import FogId, Zone
from app.schemas.reads import (
    EventSort,
    MachineId,
    Page,
    Priority,
    TaskEventRead,
    TaskRead,
    TaskSort,
    TaskStatus,
    TaskType,
)
from app.services.reads import READ_RESPONSES, filter_time, ordered, read_one, read_page

router = APIRouter(tags=["tasks"], responses=READ_RESPONSES)


@router.get("/tasks", response_model=Page[TaskRead])
async def tasks(
    origin_fog_id: FogId | None = None,
    current_fog_id: FogId | None = None,
    machine_id: MachineId | None = None,
    zone: Zone | None = None,
    status: TaskStatus | None = None,
    task_type: TaskType | None = None,
    priority: Priority | None = None,
    critical: bool | None = None,
    sort: TaskSort = "-created_at",
    window: TimeRange = Depends(),
    page: PageParams = Depends(),
    session: AsyncSession = Depends(get_session),
) -> Page[TaskRead]:
    query = select(Task)
    for column, value in (
        (Task.origin_fog_id, origin_fog_id),
        (Task.current_fog_id, current_fog_id),
        (Task.machine_id, machine_id),
        (Task.status, status),
        (Task.task_type, task_type),
        (Task.priority, priority),
        (Task.critical, critical),
    ):
        if value is not None:
            query = query.where(column == value)
    if zone is not None:
        query = query.where(Task.origin_fog_id == f"FOG_{zone}")
    query = filter_time(query, Task.created_at, window)
    query = ordered(
        query,
        sort,
        {
            "created_at": Task.created_at,
            "last_received_at": Task.last_received_at,
        },
        Task.task_id,
    )
    return await read_page(session, query, page, TaskRead)


# Route fixe avant /tasks/{task_id} : "events" n'est pas un UUID de tache.
@router.get("/tasks/events", response_model=Page[TaskEventRead])
async def task_events(
    task_id: UUID4 | None = None,
    source_fog: FogId | None = None,
    destination_fog: FogId | None = None,
    zone: Zone | None = None,
    status: TaskStatus | None = None,
    critical: bool | None = None,
    time_field: Literal["created_at", "received_at", "occurred_at"] = "created_at",
    sort: EventSort = "-received_at",
    window: TimeRange = Depends(),
    page: PageParams = Depends(),
    session: AsyncSession = Depends(get_session),
) -> Page[TaskEventRead]:
    query = select(TaskEvent).join(Task, TaskEvent.task_id == Task.task_id)
    for column, value in (
        (TaskEvent.task_id, str(task_id) if task_id is not None else None),
        (TaskEvent.source_fog, source_fog),
        (TaskEvent.destination_fog, destination_fog),
        (TaskEvent.status, status),
        (TaskEvent.critical, critical),
    ):
        if value is not None:
            query = query.where(column == value)
    if zone is not None:
        query = query.where(Task.origin_fog_id == f"FOG_{zone}")
    times = {
        "created_at": TaskEvent.created_at,
        "received_at": TaskEvent.received_at,
        "occurred_at": TaskEvent.occurred_at,
    }
    query = filter_time(query, times[time_field], window)
    query = ordered(query, sort, {**times, "id": TaskEvent.id}, TaskEvent.id)
    return await read_page(session, query, page, TaskEventRead)


@router.get("/tasks/{task_id}", response_model=TaskRead)
async def task_detail(task_id: UUID4, session: AsyncSession = Depends(get_session)) -> TaskRead:
    return await read_one(
        session,
        select(Task).where(Task.task_id == str(task_id)),
        TaskRead,
        f"Unknown task {task_id}",
    )
