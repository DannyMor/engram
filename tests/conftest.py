"""Shared test fixtures."""

import pytest

from engram.core.models import EngramConfig
from engram.storage.memory import InMemoryPreferenceStore


@pytest.fixture
def store() -> InMemoryPreferenceStore:
    return InMemoryPreferenceStore()


@pytest.fixture
def test_config() -> EngramConfig:
    return EngramConfig()
