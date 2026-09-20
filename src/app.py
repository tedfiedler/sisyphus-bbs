"""Sisyphus BBS — application entry point.

Initialize the database, configure TLS (if certificates are present),
and start the Uvicorn web server hosting the FastAPI application.
"""

import asyncio
import logging
import sys
from pathlib import Path

import uvicorn

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import config
from lib.db import get_db, close_db
from lib.logging_config import setup_logging

logger = logging.getLogger(__name__)


async def main():
    """Initialize the database and start the web server.

    If TLS certificate and key files exist at the configured paths,
    Uvicorn is started with HTTPS enabled. Otherwise it falls back
    to plain HTTP.
    """
    setup_logging()

    if config.SECRET_KEY == config.DEFAULT_SECRET_KEY:
        logger.warning(
            "SISYPHUS_SECRET is not set; using the built-in default key. "
            "Set it to a long random value in the environment or .env."
        )

    # Initialize database
    await get_db()
    logger.info("Database initialized at %s", config.DB_PATH)

    # Start web server — use HTTPS if certs are present
    ssl_args = {}
    if config.SSL_CERTFILE.exists() and config.SSL_KEYFILE.exists():
        ssl_args["ssl_certfile"] = str(config.SSL_CERTFILE)
        ssl_args["ssl_keyfile"] = str(config.SSL_KEYFILE)
        proto = "https"
    else:
        proto = "http"

    uv_config = uvicorn.Config(
        "lib.web_server:app",
        host=config.WEB_HOST,
        port=config.WEB_PORT,
        log_level="info",
        # Chat frames are a few KB at most; the 16 MB default lets a client
        # make the server buffer and parse far more than it will ever accept.
        ws_max_size=64 * 1024,
        **ssl_args,
    )
    server = uvicorn.Server(uv_config)

    logger.info("=" * 50)
    logger.info("  %s", config.BBS_NAME)
    logger.info("  Web:  %s://%s:%s", proto, config.WEB_HOST, config.WEB_PORT)
    logger.info("=" * 50)

    try:
        await server.serve()
    finally:
        await close_db()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down Sisyphus BBS...")
