"""Shared test fixtures."""

import pytest

from engram.core.models import EngramConfig
from engram.storage.memory import InMemoryImprintStore


@pytest.fixture
def store() -> InMemoryImprintStore:
    return InMemoryImprintStore()


@pytest.fixture
def test_config() -> EngramConfig:
    return EngramConfig()
