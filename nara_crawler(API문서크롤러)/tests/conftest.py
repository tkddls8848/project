import sys
from pathlib import Path

# 디렉터리명에 한글·괄호가 있어 패키지 import가 불가하므로
# 크롤러 루트를 sys.path에 넣고 managers 패키지로 import한다.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
