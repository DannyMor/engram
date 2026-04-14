"""First-run setup for engram: config, model download, environment validation."""

import os
import sys

from engram.core.config import ENGRAM_HOME, USER_CONFIG_PATH, ensure_engram_home, save_config
from engram.core.models import EngramConfig


def run_setup(skip_model_download: bool = False) -> None:
    """Run first-time setup for engram."""
    _print("Setting up engram...\n")

    # 1. Create directory structure
    ensure_engram_home()
    _print(f"  Created {ENGRAM_HOME}/")

    # 2. Create default config if not present
    if not USER_CONFIG_PATH.exists():
        save_config(EngramConfig())
        _print(f"  Created {USER_CONFIG_PATH}")
    else:
        _print(f"  Config already exists at {USER_CONFIG_PATH}")

    # 3. Download fastembed model
    if not skip_model_download:
        _print("\n  Downloading embedding model (first time only)...")
        try:
            from fastembed import TextEmbedding

            TextEmbedding(model_name=EngramConfig().embedder.model)
            _print("  Model downloaded successfully.")
        except Exception as e:
            _print(f"  Warning: Could not download model: {e}")

    # 4. Check API key
    _print("")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        _print("  ANTHROPIC_API_KEY is set.")
    else:
        _print("  ANTHROPIC_API_KEY is not set.")
        _print("  (Optional — needed for curation agent. Basic CRUD works without it.)")

    # 5. Print next steps
    _print("\nSetup complete! Next steps:\n")
    _print("  # Register with Claude Code:")
    _print("  claude mcp add engram -- uvx engramd\n")
    _print("  # Or start the web UI:")
    _print("  engramd serve\n")


def _print(msg: str) -> None:
    """Print to stderr (safe in all modes)."""
    print(msg, file=sys.stderr)
