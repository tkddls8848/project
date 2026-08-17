import sys
from pathlib import Path

# 크롤러 루트는 설치되는 패키지가 아니다. managers·crawler·utils 등을 최상위
# 이름으로 import하므로 루트 자체를 sys.path에 넣는다.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

LIBS_DIR = PROJECT_ROOT.parents[1] / "libs"
if str(LIBS_DIR) not in sys.path:
    sys.path.insert(0, str(LIBS_DIR))
