from __future__ import annotations

import sys
from pathlib import Path

# 실행기들과 같은 자리를 sys.path에 넣는다. CWD가 어디든 nara_common이 풀린다.
LIBS_DIR = Path(__file__).resolve().parents[1] / "libs"
if str(LIBS_DIR) not in sys.path:
    sys.path.insert(0, str(LIBS_DIR))
