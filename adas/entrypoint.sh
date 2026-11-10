#!/bin/bash
# ==============================================================================
# Subsystem: ADAS Container Entrypoint & Device Healthcheck
# Upstream Reference: https://github.com/Thorn-probably/adas
# Architecture: Powered by cl0ud (https://github.com/Ojas-sta/cl0ud-brand-engineering)
# Co-Engineered by: Ojas Singh <ojasctc@gmail.com>
# ==============================================================================
set -e

echo "=============================================================================="
echo "   ADAS DRIVER MONITORING SYSTEM (DMS) — CONTAINER INITIALIZATION"
echo "   Target Platform: Raspberry Pi 4B (ARM64 / Cortex-A72) & Desktop"
echo "   Upstream Source: https://github.com/Thorn-probably/adas"
echo "   Architecture: Powered by cl0ud (https://github.com/Ojas-sta/cl0ud-brand-engineering)"
echo "   Co-Engineered by: Ojas Singh <ojasctc@gmail.com>"
echo "=============================================================================="

# 1. Model Asset Verification
if [ -f "/app/models/face_landmarker.task" ] && [ $(wc -c < "/app/models/face_landmarker.task") -gt 1000 ]; then
    echo "[DMS-Init] MediaPipe neural face landmarker verified in /app/models/."
else
    echo "[DMS-Init] MediaPipe model missing or empty. Fetching offline model asset..."
    python /app/download_models.py
fi

# 2. Camera Device Verification
if [ -e "/dev/video0" ]; then
    echo "[DMS-Init] Hardware Camera detected at /dev/video0."
else
    echo "[DMS-Init] Notice: /dev/video0 not detected."
    echo "[DMS-Init] To test without physical camera, provide --video /app/test_videos/test_eyes_closed.mp4"
fi

# 3. Hardware GPIO Verification
if [ -e "/dev/gpiomem" ]; then
    echo "[DMS-Init] Raspberry Pi /dev/gpiomem detected. Active hardware GPIO buzzer (Pin 18) ready."
elif [ -e "/dev/gpiochip0" ] || [ -e "/dev/gpiochip4" ]; then
    echo "[DMS-Init] Linux gpiochip interface detected."
fi

# 4. Audio Soundcard Verification
if [ -e "/dev/snd" ]; then
    echo "[DMS-Init] ALSA audio output device detected at /dev/snd."
fi

echo "[DMS-Init] Starting DMS Execution: $@"
echo "------------------------------------------------------------------------------"
exec "$@"
