"""Natural-language API document search web service."""

import sys
from pathlib import Path

LIBS_DIR = Path(__file__).resolve().parents[3] / "libs"
if str(LIBS_DIR) not in sys.path:
    sys.path.insert(0, str(LIBS_DIR))
