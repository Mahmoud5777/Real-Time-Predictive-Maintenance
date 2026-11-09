"""Contrat des lectures : validation avant SQL, erreurs et documentation."""

from unittest.mock import AsyncMock

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db.session import get_session
from app.main import create_app
from scripts.export_openapi import CONTRACT, build_contract

COLLECTIONS = [
    "/machines",
    "/measurements",
    "/predictions",
    "/alerts",
    "/fog/nodes",
    "/fog/status-history",
    "/fog/supervision-history",
    "/tasks",
    "/tasks/events",
]
TIMED = [
    "/measurements",
    "/predictions",
    "/alerts",
    "/fog/status-history",
    "/fog/supervision-history",
    "/tasks",
    "/tasks/events",
]


@pytest.fixture
def client():
    application = create_app()
    session = AsyncMock()

    async def isolated_database():
        yield session

    application.dependency_overrides[get_session] = isolated_database
    with TestClient(application) as http:
        yield http, session


@pytest.mark.parametrize("path", COLLECTIONS)
@pytest.mark.parametrize(
    "params", [{"limit": 0}, {"limit": 1001}, {"offset": -1}, {"sort": "password"}]
)
def test_invalid_pagination_and_sort_never_execute_sql(client, path, params):
    http, session = client
    response = http.get("/api/v1" + path, params=params)
    assert response.status_code == 422
    session.execute.assert_not_awaited()


@pytest.mark.parametrize("path", TIMED)
@pytest.mark.parametrize(
    "params",
    [
        {"from": "2026-11-07T10:00:00"},
        {"to": "not-a-date"},
        {"from": "2026-11-07T11:00:00Z", "to": "2026-11-07T10:00:00Z"},
    ],
)
def test_invalid_time_range_never_executes_sql(client, path, params):
    http, session = client
    response = http.get("/api/v1" + path, params=params)
    assert response.status_code == 422
    session.execute.assert_not_awaited()


@pytest.mark.parametrize(
    "path,params",
    [
        ("/machines", {"zone": "D"}),
        ("/measurements", {"machine_id": "M99"}),
        ("/predictions", {"anomaly": "maybe"}),
        ("/predictions", {"model_version": ""}),
        ("/alerts", {"status": "DELETED"}),
        ("/alerts", {"severity": "HIGH"}),
        ("/fog/nodes", {"status": "UNKNOWN"}),
        ("/fog/status-history", {"fog_id": "FOG_D"}),
        ("/tasks", {"critical": "maybe"}),
        ("/tasks", {"priority": "URGENT"}),
        ("/tasks/events", {"task_id": "not-a-uuid"}),
        ("/tasks/events", {"task_id": "b3f1c2d4-6a11-1f3a-9c2e-7d5b1a0e9f42"}),
        ("/tasks/events", {"time_field": "timestamp"}),
    ],
)
def test_invalid_filters_never_execute_sql(client, path, params):
    http, session = client
    assert http.get("/api/v1" + path, params=params).status_code == 422
    session.execute.assert_not_awaited()


@pytest.mark.parametrize(
    "path",
    COLLECTIONS
    + [
        "/machines/M01",
        "/machines/M01/latest",
        "/alerts/unknown",
        "/fog/nodes/FOG_A",
        "/tasks/b3f1c2d4-6a11-4f3a-9c2e-7d5b1a0e9f42",
    ],
)
def test_database_failure_is_safe_503(client, path):
    http, session = client
    session.execute.side_effect = OperationalError("private SQL", {}, Exception("private DSN"))
    response = http.get("/api/v1" + path)
    assert response.status_code == 503
    assert response.json()["status"] == 503
    assert response.json()["instance"] == "/api/v1" + path
    assert "private" not in response.text
    assert "detail" in response.json() and "items" not in response.json()


def test_swagger_documents_read_models_and_write_authentication():
    schema = create_app().openapi()
    for path in COLLECTIONS:
        operation = schema["paths"]["/api/v1" + path]["get"]
        assert operation["security"] == []
        assert "$ref" in operation["responses"]["200"]["content"]["application/json"]["schema"]
        assert "503" in operation["responses"]
    assert schema["paths"]["/api/v1/ingest/batch"]["post"]["security"] == [{"BearerAuth": []}]


def test_published_read_contract_matches_running_api_and_marks_roadmap():
    current = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    assert build_contract(current) == current
    assert current["openapi"] == "3.0.3"
    assert current["paths"]["/analytics/kpis"]["get"]["x-implementation-status"] == "implemented"
    assert current["paths"]["/stream"]["get"]["x-implementation-status"] == "planned"
    assert current["paths"]["/measurements"]["get"]["x-implementation-status"] == "implemented"
