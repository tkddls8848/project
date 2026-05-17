"""CLI 래퍼 — stage99_service.cache_builder.extract() 직접 호출"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stage99_service.cache_builder import extract

if __name__ == "__main__":
    extract(force="--force" in sys.argv)
