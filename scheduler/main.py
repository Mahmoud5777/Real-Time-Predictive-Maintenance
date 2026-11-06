
import asyncio
import logging
from contextlib import asynccontextmanager
from threading import Lock
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from mqtt.mqtt_client import MQTTClient
from scheduler.node_registry import NodeRegistry
from scheduler.task_registry import TaskRegistry
from scheduler.scheduling_policy import (
    select_destination,
    calculate_node_score,
)
from shared.models import TaskRequest


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --------------------------------------------------
# Configuration
# --------------------------------------------------

FOG_NODE_URLS = {
    "fog-a": "http://127.0.0.1:8001",
    "fog-b": "http://127.0.0.1:8002",
    "fog-c": "http://127.0.0.1:8003",
}


# --------------------------------------------------
# Request models
# --------------------------------------------------

class DispatchRequest(BaseModel):
    source_fog_id: str
    task: TaskRequest


class TaskStatusUpdate(BaseModel):
    status: Literal[
        "PENDING",
        "ACCEPTED",
        "RUNNING",
        "MIGRATED",
        "COMPLETED",
        "FAILED",
        "RECOVERED",
    ]


# --------------------------------------------------
# Initialize Scheduler components
# --------------------------------------------------

node_registry = NodeRegistry(offline_timeout=15)
task_registry = TaskRegistry()

mqtt_client = MQTTClient(
    client_id="central-scheduler",
    broker_host="127.0.0.1",
    broker_port=1883,
)

# Events received before task registration are temporarily stored here.
pending_task_events = {}
pending_events_lock = Lock()


# --------------------------------------------------
# MQTT event handlers
# --------------------------------------------------

def handle_task_event(payload: dict):
    """
    Receive task lifecycle events from Fog nodes
    and update the central task registry.
    """

    task_id = payload.get("task_id")
    status = payload.get("status")

    if not task_id or not status:
        logger.warning("Received an invalid task event: %s", payload)
        return

    with pending_events_lock:
        registered_task = task_registry.get_task(task_id)

        if registered_task is None:
            # The Fog node may process the task before the
            # dispatch endpoint finishes registering it.
            pending_task_events[task_id] = payload

            logger.info(
                "Task event temporarily stored: %s (%s)",
                task_id,
                status,
            )
            return

        task_registry.update_task_status(task_id, status)

    logger.info(
        "Task %s status updated through MQTT: %s",
        task_id,
        status,
    )


# --------------------------------------------------
# Node monitoring
# --------------------------------------------------

async def monitor_nodes():
    """Periodically detect Fog nodes that stopped sending heartbeats."""

    while True:
        offline_nodes = node_registry.check_offline_nodes()

        for fog_id in offline_nodes:
            logger.warning("Fog node %s is OFFLINE", fog_id)

        await asyncio.sleep(2)


# --------------------------------------------------
# Application lifespan
# --------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Central Scheduler...")

    mqtt_client.subscribe(
        "fog/+/status",
        node_registry.update_node,
    )

    mqtt_client.subscribe(
        "fog/+/tasks/events",
        handle_task_event,
    )

    mqtt_client.connect()

    monitor_task = asyncio.create_task(monitor_nodes())

    yield

    monitor_task.cancel()

    try:
        await monitor_task
    except asyncio.CancelledError:
        pass

    mqtt_client.disconnect()

    logger.info("Central Scheduler stopped")


app = FastAPI(
    title="Collaborative Fog Scheduler",
    description="Central monitoring and dynamic scheduling service",
    version="1.0.0",
    lifespan=lifespan,
)


# --------------------------------------------------
# General endpoints
# --------------------------------------------------

@app.get("/health")
async def health():
    return {
        "service": "central-scheduler",
        "status": "running",
    }


# --------------------------------------------------
# Fog node monitoring endpoints
# --------------------------------------------------

@app.get("/nodes")
async def get_nodes():
    return node_registry.get_all_nodes()


@app.get("/nodes/{fog_id}")
async def get_node(fog_id: str):
    node = node_registry.get_node(fog_id)

    if node is None:
        raise HTTPException(
            status_code=404,
            detail=f"Fog node {fog_id} not found",
        )

    return node


# --------------------------------------------------
# Task registry endpoints
# --------------------------------------------------

@app.get("/tasks")
async def get_tasks():
    """Return all tasks registered by the scheduler."""

    return task_registry.get_all_tasks()


@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Return information about one registered task."""

    task = task_registry.get_task(task_id)

    if task is None:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found",
        )

    return task


@app.get("/nodes/{fog_id}/tasks")
async def get_node_tasks(fog_id: str):
    """Return unfinished tasks assigned to a Fog node."""

    node = node_registry.get_node(fog_id)

    if node is None:
        raise HTTPException(
            status_code=404,
            detail=f"Fog node {fog_id} not found",
        )

    return task_registry.get_node_tasks(fog_id)


@app.patch("/tasks/{task_id}/status")
async def update_task_status(
    task_id: str,
    request: TaskStatusUpdate,
):
    """Manually update the lifecycle status of a task."""

    updated = task_registry.update_task_status(
        task_id,
        request.status,
    )

    if not updated:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found",
        )

    logger.info(
        "Task %s status manually updated to %s",
        task_id,
        request.status,
    )

    return {
        "task_id": task_id,
        "status": request.status,
        "message": "Task status updated successfully",
    }


# --------------------------------------------------
# Scheduling endpoint (decision only)
# --------------------------------------------------

@app.post("/schedule")
async def schedule_task(task: dict):
    required_fields = {
        "task_id",
        "priority",
        "source_fog_id",
    }

    if not required_fields.issubset(task):
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: task_id, priority, source_fog_id",
        )

    source_fog_id = task["source_fog_id"]

    source_node = node_registry.get_node(source_fog_id)

    if source_node is None:
        raise HTTPException(
            status_code=404,
            detail=f"Source Fog node {source_fog_id} not found",
        )

    if source_node["availability"] != "ONLINE":
        raise HTTPException(
            status_code=503,
            detail=f"Source Fog node {source_fog_id} is unavailable",
        )

    destination = select_destination(
        task_priority=task["priority"],
        source_fog_id=source_fog_id,
        nodes=node_registry.get_all_nodes(),
    )

    if destination is None:
        return {
            "task_id": task["task_id"],
            "source_fog_id": source_fog_id,
            "destination_fog_id": source_fog_id,
            "decision": "LOCAL_EXECUTION",
            "reason": "No suitable migration destination or HIGH priority",
        }

    return {
        "task_id": task["task_id"],
        "source_fog_id": source_fog_id,
        "destination_fog_id": destination["fog_id"],
        "decision": "MIGRATION",
        "destination_score": round(
            calculate_node_score(destination),
            2,
        ),
    }


# --------------------------------------------------
# Task dispatching
# --------------------------------------------------

async def dispatch_task(request: DispatchRequest):
    """Schedule, dispatch and register a task."""

    source_fog_id = request.source_fog_id
    task = request.task

    source_node = node_registry.get_node(source_fog_id)

    if source_node is None:
        raise HTTPException(
            status_code=404,
            detail=f"Source Fog node {source_fog_id} not found",
        )

    if source_node["availability"] != "ONLINE":
        raise HTTPException(
            status_code=503,
            detail=f"Source Fog node {source_fog_id} is unavailable",
        )

    if source_fog_id not in FOG_NODE_URLS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown source Fog node {source_fog_id}",
        )

    # Preserve the original source of the task.
    task.source_fog = source_fog_id

    destination = select_destination(
        task_priority=task.priority,
        source_fog_id=source_fog_id,
        nodes=node_registry.get_all_nodes(),
    )

    if destination is None:
        destination_fog_id = source_fog_id
        endpoint = "/tasks/local"
        decision = "LOCAL_EXECUTION"
    else:
        destination_fog_id = destination["fog_id"]
        endpoint = "/tasks/receive"
        decision = "MIGRATION"

    destination_url = FOG_NODE_URLS.get(destination_fog_id)

    if destination_url is None:
        raise HTTPException(
            status_code=500,
            detail=f"No API URL configured for {destination_fog_id}",
        )

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{destination_url}{endpoint}",
                json=task.model_dump(mode="json"),
            )

            response.raise_for_status()

    except httpx.TimeoutException:
        logger.error(
            "Dispatch timeout for task %s to %s",
            task.task_id,
            destination_fog_id,
        )

        raise HTTPException(
            status_code=504,
            detail="Destination Fog node did not respond in time",
        )

    except httpx.HTTPStatusError as exc:
        logger.error(
            "Dispatch rejected for task %s: %s",
            task.task_id,
            exc.response.text,
        )

        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Destination rejected task: {exc.response.text}",
        )

    except httpx.RequestError as exc:
        logger.error(
            "Cannot reach destination %s: %s",
            destination_fog_id,
            str(exc),
        )

        raise HTTPException(
            status_code=503,
            detail=f"Cannot reach Fog node {destination_fog_id}",
        )

    # Register the task and process any event that arrived
    # before the registration was completed.
    with pending_events_lock:
        task_registry.register_task(
            task=task.model_dump(mode="json"),
            source_fog=source_fog_id,
            destination_fog=destination_fog_id,
        )

        pending_event = pending_task_events.pop(
            task.task_id,
            None,
        )

        if pending_event is not None:
            task_registry.update_task_status(
                task.task_id,
                pending_event["status"],
            )

            logger.info(
                "Pending event applied to task %s: %s",
                task.task_id,
                pending_event["status"],
            )

    logger.info(
        "Task %s dispatched from %s to %s (%s)",
        task.task_id,
        source_fog_id,
        destination_fog_id,
        decision,
    )

    result = {
        "task_id": task.task_id,
        "source_fog_id": source_fog_id,
        "destination_fog_id": destination_fog_id,
        "decision": decision,
        "destination_response": response.json(),
        "registry_status": task_registry.get_task(task.task_id)["status"],
    }

    if destination is not None:
        result["destination_score"] = round(
            calculate_node_score(destination),
            2,
        )

    return result


@app.post("/dispatch")
async def dispatch_endpoint(request: DispatchRequest):
    return await dispatch_task(request)
