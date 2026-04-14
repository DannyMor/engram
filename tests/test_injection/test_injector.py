"""Tests for the session injector module."""

from engram.injection.injector import detect_scopes_from_extensions, format_injection_block
from engram.core.models import Confidence, Preference, Source


def test_format_injection_block_with_prefs():
    prefs = [
        Preference(
            id="1",
            text="Use pytest fixtures",
            scope="python",
            source=Source.MANUAL,
            confidence=Confidence.HIGH,
        ),
        Preference(
            id="2",
            text="Prefer frozen dataclasses",
            scope="python",
            source=Source.MANUAL,
            confidence=Confidence.HIGH,
        ),
    ]
    block = format_injection_block(prefs)
    assert "<!-- engram:start -->" in block
    assert "<!-- engram:end -->" in block
    assert "- Use pytest fixtures" in block
    assert "- Prefer frozen dataclasses" in block


def test_format_injection_block_empty():
    block = format_injection_block([])
    assert block == ""


def test_detect_scopes_from_extensions():
    extensions = {".py", ".pyx"}
    scopes = detect_scopes_from_extensions(extensions)
    assert "python" in scopes
    assert "global" in scopes


def test_detect_scopes_multiple_languages():
    extensions = {".py", ".ts", ".tsx"}
    scopes = detect_scopes_from_extensions(extensions)
    assert "python" in scopes
    assert "typescript" in scopes
    assert "global" in scopes


def test_detect_scopes_with_test_files():
    extensions = {".py"}
    scopes = detect_scopes_from_extensions(extensions, has_test_files=True)
    assert "testing" in scopes


def test_detect_scopes_unknown_extension():
    extensions = {".xyz"}
    scopes = detect_scopes_from_extensions(extensions)
    assert scopes == ["global"]
