"""Entry point for running the engram server."""

import uvicorn

from engram.app import create_app
from engram.core.config import load_config
from engram.core.logging import setup_logging


def main() -> None:
    config = load_config()
    setup_logging(config.logging.level)
    app = create_app(config=config)
    uvicorn.run(app, host=config.server.host, port=config.server.port)


if __name__ == "__main__":
    main()
