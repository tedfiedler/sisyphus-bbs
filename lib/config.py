import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DB_PATH = os.getenv("SISYPHUS_DB", str(BASE_DIR / "db" / "sisyphus.db"))
SECRET_KEY = os.getenv("SISYPHUS_SECRET", "change-me-in-production")
WEB_HOST = os.getenv("SISYPHUS_WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("SISYPHUS_WEB_PORT", "8000"))
SSH_HOST = os.getenv("SISYPHUS_SSH_HOST", "0.0.0.0")
SSH_PORT = int(os.getenv("SISYPHUS_SSH_PORT", "2222"))
SSH_HOST_KEY = os.getenv("SISYPHUS_SSH_KEY", str(BASE_DIR / "ssh_host_key"))
FILE_STORE = Path(os.getenv("SISYPHUS_FILES", str(BASE_DIR / "file_store")))
BBS_NAME = os.getenv("SISYPHUS_NAME", "Sisyphus BBS")
SESSION_EXPIRY_HOURS = int(os.getenv("SISYPHUS_SESSION_HOURS", "24"))

TEMPLATES_DIR = BASE_DIR / "frontend" / "templates"
STATIC_DIR = BASE_DIR / "frontend" / "static"
ANSI_ART_DIR = BASE_DIR / "ansi_art"
LOG_DIR = BASE_DIR / "log"
DOORS_DIR = BASE_DIR / "doors"
