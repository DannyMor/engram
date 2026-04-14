"""Health endpoint tests."""

from engram.api.models import HealthResponse


async def test_health(client) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200
    health = HealthResponse.model_validate(response.json())
    assert health.status == "ok"
    assert health.version == "0.1.0"
