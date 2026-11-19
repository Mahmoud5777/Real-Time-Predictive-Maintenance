from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

from app.api.analytics import router as analytics_router
from app.api.fog import router as fog_router
from app.api.health import router as health_router
from app.api.ingest import router as ingest_router
from app.api.machines import router as machines_router
from app.api.observations import router as observations_router
from app.api.tasks import router as tasks_router
from app.config import get_settings
from app.services.reads import ReadError, read_error_handler

REQUEST_COUNT = Counter(
    "fog_cloud_http_requests_total",
    "Nombre de requetes HTTP recues par le backend Cloud",
    ["route", "status"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Le worker MQTT est un processus distinct : python -m app.ingest.worker.
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="FOG Cloud API (MP3)",
        version="0.1.0",
        description=(
            "Backend Cloud centralisant machines, mesures, predictions, alertes, "
            "etat des noeuds Fog et evenements de taches."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(ingest_router, prefix=settings.api_prefix)
    app.include_router(machines_router, prefix=settings.api_prefix)
    app.include_router(observations_router, prefix=settings.api_prefix)
    app.include_router(fog_router, prefix=settings.api_prefix)
    app.include_router(tasks_router, prefix=settings.api_prefix)
    app.include_router(analytics_router, prefix=settings.api_prefix)
    app.add_exception_handler(ReadError, read_error_handler)

    def documented_openapi():
        if app.openapi_schema is None:
            schema = get_openapi(
                title=app.title, version=app.version, description=app.description, routes=app.routes
            )
            schema["components"].setdefault("securitySchemes", {})["BearerAuth"] = {
                "type": "http",
                "scheme": "bearer",
            }
            for path, operations in schema["paths"].items():
                if path.startswith(settings.api_prefix + "/"):
                    for method, operation in operations.items():
                        if method == "get":
                            operation["security"] = []
                        elif path == settings.api_prefix + "/ingest/batch" and method == "post":
                            operation["security"] = [{"BearerAuth": []}]
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = documented_openapi
    return app


app = create_app()


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Exposition Prometheus pour Grafana (MP4)."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):  # pragma: no cover
    """Erreurs normalisees RFC 7807 : le dashboard recoit toujours la meme forme."""
    return JSONResponse(
        status_code=500,
        content={
            "type": "https://fog-project/errors/internal",
            "title": "Internal Server Error",
            "status": 500,
            "detail": "Unexpected backend error",
            "instance": str(request.url.path),
        },
    )
