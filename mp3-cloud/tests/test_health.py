from fastapi.testclient import TestClient

from app.main import app


def test_healthz_ok():
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_metrics_endpoint_exposes_prometheus_text():
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "fog_cloud_http_requests_total" in response.text
