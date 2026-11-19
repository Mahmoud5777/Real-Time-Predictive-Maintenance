from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    """Health check utilise par Docker, le CI et Grafana (MP4)."""
    return {"status": "ok", "service": "mp3-cloud-api", "version": "0.1.0"}
