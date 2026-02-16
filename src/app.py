"""Sisyphus BBS - Entry point.

Starts both the web server (FastAPI/Uvicorn) and the SSH terminal server.
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
from lib.terminal_server import start_ssh_server

logger = logging.getLogger(__name__)


async def main():
    setup_logging()

    # Initialize database
    await get_db()
    logger.info("Database initialized at %s", config.DB_PATH)

    # Start SSH server
    try:
        await start_ssh_server()
    except Exception as e:
        logger.error("SSH server failed to start: %s", e)
        logger.info("Continuing with web server only...")

    # Start web server
    uv_config = uvicorn.Config(
        "lib.web_server:app",
        host=config.WEB_HOST,
        port=config.WEB_PORT,
        log_level="info",
    )
    server = uvicorn.Server(uv_config)

    logger.info("=" * 50)
    logger.info("  %s", config.BBS_NAME)
    logger.info("  Web:  http://%s:%s", config.WEB_HOST, config.WEB_PORT)
    logger.info("  SSH:  ssh -p %s %s", config.SSH_PORT, config.SSH_HOST)
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
