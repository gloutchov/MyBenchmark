from __future__ import annotations

import argparse
from pathlib import Path

from .exporter import export_markdown


def main() -> int:
    parser = argparse.ArgumentParser(prog="tinyjournal")
    subparsers = parser.add_subparsers(dest="command", required=True)
    export = subparsers.add_parser("export")
    export.add_argument("journal", type=Path)
    export.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "export":
        export_markdown(Path.cwd(), args.journal, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
