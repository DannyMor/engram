"""First-run setup for engram: config, model download, environment validation."""

import os
import sys

import yaml

from engram.core.config import ENGRAM_HOME, USER_CONFIG_PATH
from engram.core.models import EngramConfig


def run_setup(skip_model_download: bool = False) -> None:
    """Run first-time setup for engram."""
    _print("Setting up engram...\n")

    # 1. Create directory structure
    ENGRAM_HOME.mkdir(parents=True, exist_ok=True)
    (ENGRAM_HOME / "data").mkdir(exist_ok=True)
    (ENGRAM_HOME / "logs").mkdir(exist_ok=True)
    _print(f"  Created {ENGRAM_HOME}/")

    # 2. Create default config if not present
    if not USER_CONFIG_PATH.exists():
        config = EngramConfig()
        data = config.model_dump()
        with open(USER_CONFIG_PATH, "w") as f:
            yaml.dump(data, f, default_flow_style=False)
        _print(f"  Created {USER_CONFIG_PATH}")
    else:
        _print(f"  Config already exists at {USER_CONFIG_PATH}")

    # 3. Download fastembed model
    if not skip_model_download:
        _print("\n  Downloading embedding model (first time only)...")
        try:
            from fastembed import TextEmbedding

            TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
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
    _print("  claude mcp add engram -- uvx engram-ai\n")
    _print("  # Or start the web UI:")
    _print("  engram serve\n")


def _print(msg: str) -> None:
    """Print to stderr (safe in all modes)."""
    print(msg, file=sys.stderr)
