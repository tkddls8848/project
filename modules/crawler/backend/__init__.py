"""브라우저용 크롤러 제어 서비스.

크롤러 루트와 `libs/`를 sys.path에 넣는다. 백엔드는 크롤러 모듈(`main`,
`managers`)과 공용 유틸리티(`nara_common`)를 모두 쓰는데, uvicorn으로 바로
띄우면 둘 다 import 경로에 없다. 진입점이 무엇이든 같게 동작하도록 여기서 맞춘다.
"""

import sys
from pathlib import Path

CRAWLER_ROOT = Path(__file__).resolve().parent.parent
LIBS_DIR = CRAWLER_ROOT.parents[1] / "libs"

for _path in (CRAWLER_ROOT, LIBS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
