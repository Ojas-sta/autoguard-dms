#!/usr/bin/env python3
"""
Top-level entry point forwarding to driver_monitor.main.
Supports running:
    python main.py --platform macos
    python main.py --platform raspberrypi
    python main.py --video driver_monitor/resources/videos/test_eyes_closed.mp4
    python main.py --headless
"""

import sys
import os

# Add root directory to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from driver_monitor.main import main

if __name__ == "__main__":
    main()
