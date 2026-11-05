
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from shared.models import TaskRequest, TaskStatus

from .config import config
from ..common.queue_manager import QueueManager
from ..common.processor import TaskProcessor
from ..common.monitor import ResourceMonitor


# Initialize Fog components
queue_manager = QueueManager(config)
processor = TaskProcessor(queue_manager, config)
monitor = ResourceMonitor(config)

# Store processed task events
task_history = []


async def task_worker():
    """Continuously retrieve and process tasks."""

    while True:
        event = await processor.process_next()
        task_history.append(event)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage Fog application lifecycle."""

    worker = asyncio.create_task(task_worker())

    yield

    worker.cancel()

    try:
        await worker
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title=f"Fog Node {config.fog_id}",
    description="Collaborative Fog Computing API",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health():
    return {
        "message": "Fog Node is running",
        "fog_id": config.fog_id
    }


@app.get("/status")
async def get_status():

    status = monitor.get_status(
        queued_tasks=queue_manager.get_queue_size()
    )

    return status


@app.post("/tasks", status_code=202)
async def submit_task(task: TaskRequest):

    try:
        queue_manager.add_task(task)

    except asyncio.QueueFull:
        raise HTTPException(
            status_code=503,
            detail="Fog queue is full"
        )

    return {
        "message": "Task accepted",
        "task_id": task.task_id,
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
