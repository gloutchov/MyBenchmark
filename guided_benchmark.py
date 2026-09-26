#!/usr/bin/env python3
"""Double-clickable GUI entry point for the guided benchmark funnel."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from localagent_bench.guided_ui import main


if __name__ == "__main__":
    raise SystemExit(main())
