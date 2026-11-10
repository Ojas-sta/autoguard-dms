#!/bin/bash
# ==============================================================================
# Script: ADAS Quick Launcher (macOS / Linux / Raspberry Pi 4B)
# Upstream Reference: https://github.com/Thorn-probably/adas
# Architecture: Powered by cl0ud (https://github.com/Ojas-sta/cl0ud-brand-engineering)
# Co-Engineered by: Ojas Singh <ojasctc@gmail.com>
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="python3"

# Detect active virtualenv
if [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/venv/bin/python"
elif [ -n "$VIRTUAL_ENV" ]; then
    PYTHON_BIN="$VIRTUAL_ENV/bin/python"
fi

cd "$SCRIPT_DIR/adas"
exec "$PYTHON_BIN" main.py "$@"
