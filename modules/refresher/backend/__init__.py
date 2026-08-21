"""브라우저용 연장 제어 서비스.

refresher 루트와 `libs/`를 sys.path에 넣는다. uvicorn으로 바로 띄우면 `app`
패키지와 `nara_common`이 import 경로에 없다. 진입점이 무엇이든 같게 동작하도록
여기서 맞춘다 (tests/conftest.py와 같은 처리다).
"""

import sys
from pathlib import Path

REFRESHER_ROOT = Path(__file__).resolve().parent.parent
LIBS_DIR = REFRESHER_ROOT.parents[1] / "libs"

for _path in (REFRESHER_ROOT, LIBS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
