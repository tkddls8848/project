"""CLI 래퍼 — stage99_service.cache_builder.build_index() 직접 호출"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stage99_service.cache_builder import extract, build_index

if __name__ == "__main__":
    force = "--force" in sys.argv
    extract(force=force)
    build_index(force=force)
