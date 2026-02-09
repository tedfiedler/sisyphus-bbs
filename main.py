"""Sisyphus BBS - Entry point.

Starts both the web server (FastAPI/Uvicorn) and the SSH terminal server.
"""

import asyncio
import signal
import sys

import uvicorn

import config
from db import get_db, close_db
from terminal_server import start_ssh_server


async def main():
    # Initialize database
    await get_db()
    print(f"Database initialized at {config.DB_PATH}")

    # Start SSH server
    try:
        await start_ssh_server()
    except Exception as e:
        print(f"SSH server failed to start: {e}")
        print("Continuing with web server only...")

    # Start web server
    uv_config = uvicorn.Config(
        "web_server:app",
        host=config.WEB_HOST,
        port=config.WEB_PORT,
        log_level="info",
    )
    server = uvicorn.Server(uv_config)

    print(f"\n{'=' * 50}")
    print(f"  {config.BBS_NAME}")
    print(f"  Web:  http://{config.WEB_HOST}:{config.WEB_PORT}")
    print(f"  SSH:  ssh -p {config.SSH_PORT} {config.SSH_HOST}")
    print(f"{'=' * 50}\n")

    try:
        await server.serve()
    finally:
        await close_db()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down Sisyphus BBS...")
