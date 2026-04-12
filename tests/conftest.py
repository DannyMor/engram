"""Shared test fixtures for engram."""

from pathlib import Path

import pytest

from engram.models import EmbedderConfig, EngramConfig, LLMConfig, StorageConfig


@pytest.fixture
def tmp_storage(tmp_path: Path) -> Path:
    """Provide a temporary directory for Qdrant storage."""
    storage_dir = tmp_path / "data"
    storage_dir.mkdir()
    return storage_dir


@pytest.fixture
def test_config(tmp_storage: Path) -> EngramConfig:
    """Provide a test configuration with temporary storage."""
    return EngramConfig(
        storage=StorageConfig(path=str(tmp_storage)),
        llm=LLMConfig(provider="anthropic", model="claude-sonnet-4-6"),
        embedder=EmbedderConfig(provider="fastembed", model="BAAI/bge-small-en-v1.5"),
    )
