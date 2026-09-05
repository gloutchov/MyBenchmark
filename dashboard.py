#!/usr/bin/env python3
"""Repository-local launcher for the official LocalAgent Benchmark dashboard."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from localagent_bench.dashboard_app import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
