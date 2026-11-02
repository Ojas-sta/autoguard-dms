# AutoGuard DMS — Docker Containerization
# Multi-platform support: linux/amd64 and linux/arm64 (Raspberry Pi 4B)

FROM python:3.11-slim-bookworm

# Set metadata
LABEL maintainer="AutoGuard DMS Team"
LABEL architecture="Powered by cl0ud (https://github.com/Ojas-sta/cl0ud-brand-engineering)"
LABEL co-engineered-by="Ojas Singh <ojasctc@gmail.com>"
LABEL description="Exhibition-ready Driver Monitoring System (Drowsiness, Road Gaze & Distraction Detection)"

# Prevent interactive prompts and Python output buffering
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    QT_QPA_PLATFORM=offscreen

# Install system dependencies for OpenCV, MediaPipe, audio, and camera access
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1 \
    libglib2.0-0 \
    libasound2 \
    v4l-utils \
    libusb-1.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root system user with video and dialout access
RUN groupadd -g 1000 autoguard && \
    useradd -u 1000 -g autoguard -G video,dialout -m -s /bin/bash autoguard

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY driver_monitor/ /app/driver_monitor/
COPY resources/ /app/resources/
COPY main.py .

# Create logs and output directories with proper permissions
RUN mkdir -p /app/logs /app/driver_monitor/profiles && \
    chown -R autoguard:autoguard /app

USER autoguard

# Default entrypoint runs the headless benchmark or verification
CMD ["python", "-m", "driver_monitor.benchmark", "--profile", "BALANCED", "--duration", "30.0"]
