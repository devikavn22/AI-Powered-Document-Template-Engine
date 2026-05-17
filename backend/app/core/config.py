import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from backend/app/.env (sibling of this package) without overriding
# anything already set in the real process environment (e.g. docker-compose).
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _ENV_PATH.is_file():
    load_dotenv(_ENV_PATH, override=False)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./data/uploads")
GENERATED_DIR = os.getenv("GENERATED_DIR", "./data/generated")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))

# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(GENERATED_DIR, exist_ok=True)