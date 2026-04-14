"""Config endpoint tests."""

from engram.api.models import ConfigResponse


async def test_get_config(client) -> None:
    response = await client.get("/api/config")
    assert response.status_code == 200
    config = ConfigResponse.model_validate(response.json())
    assert config.llm.provider == "anthropic"
    assert config.embedder.provider == "fastembed"
