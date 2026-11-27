from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "kroma-api"
    assert "version" in data


def test_v1_and_api_v1_health_endpoints(client: TestClient) -> None:
    for path in ("/v1/health", "/api/v1/health"):
        response = client.get(path)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["db"] == "ok"
        assert data["database"] == "sqlite"
        assert data["storage"] == "local"
        assert "version" in data
