#!/bin/zsh

set -eu
SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR/.."
exec /usr/bin/env python3 guided_benchmark.py
