
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException

from shared.models import TaskRequest, TaskStatus

from .config import config
from ..common.queue_manager import QueueManager
from ..common.processor import TaskProcessor
from ..common.monitor import ResourceMonitor
from mqtt.mqtt_client import MQTTClient


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



# Initialize Fog components
queue_manager = QueueManager(config)

monitor = ResourceMonitor(config)

# Initialize MQTT client
mqtt_client = MQTTClient(
    client_id=config.fog_id,
    broker_host="127.0.0.1",
    broker_port=1883,
)

# Initialize task processor
processor = TaskProcessor(
    queue_manager=queue_manager,
    config=config,
    mqtt_client=mqtt_client,
)

# Store processed task events
task_history = []


async def task_worker():
    """Continuously retrieve and process tasks."""

    while True:
        event = await processor.process_next()
        task_history.append(event)


async def heartbeat_worker():
    """Periodically publish Fog C status through MQTT."""

    while True:
        status = await asyncio.to_thread(
            monitor.get_status,
            queued_tasks=queue_manager.get_queue_size()
        )

        payload = status.model_dump(mode="json")
        payload["zone"] = config.zone
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()

        topic = f"fog/{config.fog_id}/status"

        mqtt_client.publish(topic, payload)

        logger.info("MQTT heartbeat published: %s", topic)

        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage Fog application lifecycle."""

    logger.info("Starting %s", config.fog_id)

    # Connect to MQTT broker
    mqtt_client.connect()

    # Wait for MQTT connection
    for _ in range(50):
        if mqtt_client.client.is_connected():
            break
        await asyncio.sleep(0.1)

    if mqtt_client.client.is_connected():
        logger.info("Connected to MQTT broker")
    else:
        logger.warning("MQTT broker connection not confirmed")

    # Start background workers
    worker = asyncio.create_task(task_worker())
    heartbeat = asyncio.create_task(heartbeat_worker())

    yield

    # Stop background workers
    worker.cancel()
    heartbeat.cancel()

    await asyncio.gather(
        worker,
        heartbeat,
        return_exceptions=True
    )

    # Disconnect MQTT
    mqtt_client.disconnect()

    logger.info("Stopped %s", config.fog_id)


app = FastAPI(
    title=f"Fog Node {config.fog_id}",
    description="Collaborative Fog Computing API - Zone C",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health():
    return {
        "message": "Fog Node is running",
        "fog_id": config.fog_id,
        "zone": config.zone
    }


@app.get("/status")
async def get_status():

    return monitor.get_status(
        queued_tasks=queue_manager.get_queue_size()
    )


@app.post("/tasks", status_code=202)
async def submit_task(task: TaskRequest):

    try:
        accepted = queue_manager.add_task(task)

        if not accepted:
            raise HTTPException(
                status_code=409,
                detail="Task already known by this Fog node"
            )

    except asyncio.QueueFull:
        raise HTTPException(
            status_code=503,
            detail="Fog queue is full"
        )

    return {
        "message": "Task accepted locally",
        "task_id": task.task_id,
        "fog_id": config.fog_id,
        "status": TaskStatus.PENDING
    }


@app.post("/tasks/receive", status_code=202)
async def receive_migrated_task(task: TaskRequest):
    """Receive a task migrated from another Fog node."""

    if task.source_fog is None:
        raise HTTPException(
            status_code=400,
            detail="Source Fog node is required for migrated tasks"
        )

    if task.source_fog == config.fog_id:
        raise HTTPException(
            status_code=400,
            detail="A Fog node cannot receive its own migrated task"
        )

    try:
        accepted = queue_manager.add_task(task)

        if not accepted:
            raise HTTPException(
                status_code=409,
                detail="Task already known by this Fog node"
            )

    except asyncio.QueueFull:
        raise HTTPException(
            status_code=503,
            detail="Destination Fog queue is full"
        )

    logger.info(
        "Migrated task %s received from %s",
        task.task_id,
        task.source_fog
    )

    return {
        "message": "Migrated task accepted",
        "task_id": task.task_id,
        "source_fog": task.source_fog,
        "destination_fog": config.fog_id,
        "status": TaskStatus.PENDING
    }

@app.post("/tasks/local", status_code=202)
async def receive_local_task(task: TaskRequest):
    """Enqueue a task for local execution."""

    try:
        accepted = queue_manager.add_task(task)

        if not accepted:
            raise HTTPException(
                status_code=409,
                detail="Task already known by this Fog node"
            )
    except asyncio.QueueFull:
        raise HTTPException(
            status_code=503,
            detail="Local Fog queue is full"
        )

    logger.info(
        "Local task %s accepted by %s",
        task.task_id,
        config.fog_id
    )

    return {
        "message": "Task accepted for local execution",
        "task_id": task.task_id,
        "fog_id": config.fog_id,
        "status": TaskStatus.PENDING
    }


@app.get("/tasks/queue")
async def get_queue():

    return {
        "fog_id": config.fog_id,
        "queued_tasks": queue_manager.get_queue_size(),
        "queue_full": queue_manager.is_full()
    }


@app.get("/tasks/history")
async def get_history():

    return task_history
