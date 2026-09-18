"""Application configuration loaded from environment variables.

All settings have sensible defaults for local development. Override via
environment variables or a ``.env`` file in the project root (loaded
automatically by python-dotenv).

Environment variables:
    SISYPHUS_DB            Path to the SQLite database file.
    SISYPHUS_SECRET        Secret key for cryptographic operations.
    SISYPHUS_WEB_HOST      Host address the web server binds to.
    SISYPHUS_WEB_PORT      Port the web server listens on.
    SISYPHUS_FILES         Directory for uploaded file storage.
    SISYPHUS_NAME          Display name shown in the UI header.
    SISYPHUS_SESSION_HOURS Session cookie lifetime in hours.
    SISYPHUS_SSL_CERT      Path to TLS certificate PEM file.
    SISYPHUS_SSL_KEY       Path to TLS private key PEM file.
    SISYPHUS_TRUST_PROXY   Set to 1 when running behind a reverse proxy that
                           sets X-Forwarded-For, so rate limiting can see the
                           real client address.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DB_PATH = os.getenv("SISYPHUS_DB", str(BASE_DIR / "db" / "sisyphus.db"))
SECRET_KEY = os.getenv("SISYPHUS_SECRET", "change-me-in-production")
WEB_HOST = os.getenv("SISYPHUS_WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("SISYPHUS_WEB_PORT", "8000"))
FILE_STORE = Path(os.getenv("SISYPHUS_FILES", str(BASE_DIR / "file_store")))
BBS_NAME = os.getenv("SISYPHUS_NAME", "Sisyphus BBS")
SESSION_EXPIRY_HOURS = int(os.getenv("SISYPHUS_SESSION_HOURS", "24"))
TRUST_PROXY = os.getenv("SISYPHUS_TRUST_PROXY", "").strip().lower() in {"1", "true", "yes"}

TEMPLATES_DIR = BASE_DIR / "frontend" / "templates"
STATIC_DIR = BASE_DIR / "frontend" / "static"
LOG_DIR = BASE_DIR / "log"
SSL_CERTFILE = Path(os.getenv("SISYPHUS_SSL_CERT", str(BASE_DIR / "certs" / "cert.pem")))
SSL_KEYFILE = Path(os.getenv("SISYPHUS_SSL_KEY", str(BASE_DIR / "certs" / "key.pem")))
