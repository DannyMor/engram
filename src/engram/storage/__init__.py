"""Preference storage — Protocol and implementations."""

from engram.storage.base import PreferenceStore
from engram.storage.memory import InMemoryPreferenceStore

__all__ = ["InMemoryPreferenceStore", "PreferenceStore"]
