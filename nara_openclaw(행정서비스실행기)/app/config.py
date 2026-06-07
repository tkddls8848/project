import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

NARA_DATA_DIR: Path = Path(os.getenv("NARA_DATA_DIR", str(BASE_DIR / "apidata")))
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "gemma4:e4b")
RUNS_DIR: Path = Path(os.getenv("OPENCLAW_RUNS_DIR", str(BASE_DIR / "runs")))
EXECUTOR_MODE: str = os.getenv("OPENCLAW_EXECUTOR_MODE", "dummy")
