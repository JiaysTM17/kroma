import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("KROMA_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

SQLITE_PATH = DATA_DIR / "kroma.db"
STORAGE_DIR = DATA_DIR / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

EXPORTS_DIR = DATA_DIR / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

APP_TITLE = "KROMA Intelligent Image Studio API"
APP_VERSION = "1.0.0"
DEBUG = os.getenv("KROMA_DEBUG", "false").lower() in ("true", "1", "t")
