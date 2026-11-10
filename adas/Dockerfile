# ==============================================================================
# Subsystem: ADAS Driver Monitoring System (DMS) — Docker Container
# Target Platform: Raspberry Pi 4B (ARM Cortex-A72 / linux/arm64) & Desktop
# Upstream Reference: https://github.com/Thorn-probably/adas
# Architecture: Powered by cl0ud (https://github.com/Ojas-sta/cl0ud-brand-engineering)
# Co-Engineered by: Ojas Singh <ojasctc@gmail.com>
# ==============================================================================

FROM python:3.11-slim-bookworm AS base

LABEL maintainer="cl0ud & Ojas Singh <ojasctc@gmail.com>"
LABEL upstream="https://github.com/Thorn-probably/adas"
LABEL architecture="Powered by cl0ud (https://github.com/Ojas-sta/cl0ud-brand-engineering)"
LABEL co-engineered-by="Ojas Singh <ojasctc@gmail.com>"
LABEL description="Ultra-lightweight ADAS Driver Monitoring System (DMS) for Raspberry Pi 4B & Desktop"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    QT_QPA_PLATFORM=offscreen

# Install system dependencies for OpenCV, MediaPipe, Audio ALSA, and Hardware GPIO
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    v4l-utils \
    libasound2 \
    alsa-utils \
    libgpiod2 \
    gpiod \
    && rm -rf /var/lib/apt/lists/*

# Create system user with access to video devices, audio, and hardware GPIO (GID 997 on Pi OS Bookworm)
RUN (groupadd -g 997 gpio 2>/dev/null || groupadd gpio) && \
    groupadd -g 1000 adas && \
    useradd -u 1000 -g adas -G video,audio,dialout,gpio -m -s /bin/bash adas

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code and model assets
COPY config.py .
COPY download_models.py .
COPY dms_engine.py .
COPY audio_alert.py .
COPY hud_overlay.py .
COPY main.py .
COPY train_dms_model.py .
COPY models/ /app/models/
COPY test_videos/ /app/test_videos/
COPY entrypoint.sh /app/entrypoint.sh

# Offline Model Baking: Download face_landmarker.task during image build
# Guarantees zero-network offline cold boot in in-vehicle embedded deployment
RUN python download_models.py

# Set proper ownership and permissions
RUN chmod +x /app/entrypoint.sh && \
    chown -R adas:adas /app

USER adas

ENTRYPOINT ["/app/entrypoint.sh"]

# Default: Headless Raspberry Pi 4B mode with hardware GPIO 18 buzzer (320x240, 35+ FPS)
CMD ["python", "main.py", "--headless", "--gpio-buzzer", "--width", "320", "--height", "240"]
