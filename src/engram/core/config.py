"""Configuration loader for engram."""

import logging
import os
import shutil
from pathlib import Path

import yaml

from engram.core.models import EngramConfig

logger = logging.getLogger(__name__)

ENGRAM_HOME = Path.home() / ".engram"
USER_CONFIG_PATH = ENGRAM_HOME / "config.yaml"
REPO_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config.yaml"


def ensure_engram_home() -> None:
    """Create ~/.engram/ and subdirectories if they don't exist."""
    ENGRAM_HOME.mkdir(exist_ok=True)
    (ENGRAM_HOME / "data").mkdir(exist_ok=True)
    (ENGRAM_HOME / "logs").mkdir(exist_ok=True)


def ensure_user_config() -> None:
    """Copy default config to ~/.engram/config.yaml if it doesn't exist."""
    if not USER_CONFIG_PATH.exists() and REPO_CONFIG_PATH.exists():
        shutil.copy(REPO_CONFIG_PATH, USER_CONFIG_PATH)
        logger.info(f"Copied default config to {USER_CONFIG_PATH}")


def load_config() -> EngramConfig:
    """Load configuration from ~/.engram/config.yaml, falling back to repo default."""
    ensure_engram_home()
    ensure_user_config()

    config_path = USER_CONFIG_PATH if USER_CONFIG_PATH.exists() else REPO_CONFIG_PATH

    if config_path.exists():
        with open(config_path) as f:
            raw = yaml.safe_load(f) or {}
        logger.info(f"Loaded config from {config_path}")
        return EngramConfig(**raw)

    logger.warning("No config file found, using defaults")
    return EngramConfig()


def save_config(config: EngramConfig) -> None:
    """Save configuration to ~/.engram/config.yaml."""
    ensure_engram_home()
    data = config.model_dump()
    with open(USER_CONFIG_PATH, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
    logger.info(f"Saved config to {USER_CONFIG_PATH}")


def resolve_api_key(api_key_env: str) -> str | None:
    """Resolve API key from environment, then ~/.engram/.env file."""
    key = os.environ.get(api_key_env)
    if key:
        return key

    env_file = ENGRAM_HOME / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                name, _, value = line.partition("=")
                if name.strip() == api_key_env:
                    return value.strip()

    return None
