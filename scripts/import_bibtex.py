"""Compatibility wrapper. The implementation lives in researchkb_agent_memory.import_bibtex."""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from researchkb_agent_memory.import_bibtex import *  # noqa: E402,F403
from researchkb_agent_memory.import_bibtex import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
