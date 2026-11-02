# AutoGuard DMS — Docker & Container Deployment Guide

This guide covers building and running the AutoGuard Driver Monitoring System (DMS) in Docker on macOS, Linux AMD64, and Raspberry Pi 4B (ARM64).

---

## 1. Overview & Architecture

AutoGuard DMS is containerized using multi-architecture Docker images (`linux/amd64` and `linux/arm64`).
The container runs in non-root mode (`autoguard` user) and includes dependencies for MediaPipe, OpenCV, ALSA audio, and V4L2 camera streaming.

---

## 2. Quick Start with Docker Compose

### A. Headless Benchmark & Verification (macOS / PC / Server)

Run an automated 20-second benchmark on test video:

```bash
docker compose --profile dev-video up --build
```

The resulting benchmark metrics and CSV trace will be saved to `./logs/`.

### B. Raspberry Pi 4B with USB Webcam & ESP32-S3

Run on a physical Raspberry Pi 4B with a USB camera connected at `/dev/video0`:

```bash
docker compose --profile pi-usb up --build -d
```

To view live container logs:

```bash
docker compose --profile pi-usb logs -f
```

### C. Raspberry Pi 4B with CSI Camera Module (Pi Camera V1/V2/V3)

Run with CSI hardware access:

```bash
docker compose --profile pi-csi up --build -d
```

---

## 3. Direct Docker Commands

### Build Image Locally:

```bash
docker build -t autoguard-dms:latest .
```

### Multi-Architecture Build (for cross-compiling to Raspberry Pi ARM64):

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t autoguard-dms:latest .
```

### Run Custom Benchmark Container:

```bash
docker run --rm -it \
  -v $(pwd)/logs:/app/logs \
  autoguard-dms:latest \
  python -m driver_monitor.benchmark --profile LOW_POWER --duration 15.0
```

---

## 4. Hardware Device Permissions on Linux / Raspberry Pi

When running containers with real camera hardware or ESP32 UART controllers on Linux:

1. **Camera Access:**
   Ensure user is in the `video` group:
   ```bash
   sudo usermod -a -G video $USER
   ```
   Pass `--device /dev/video0:/dev/video0` to docker.

2. **ESP32 Serial Port Access:**
   Ensure user is in the `dialout` group:
   ```bash
   sudo usermod -a -G dialout $USER
   ```
   Pass `--device /dev/ttyUSB0:/dev/ttyUSB0` to docker.
