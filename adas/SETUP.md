# Automotive ADAS Driver Monitoring System (DMS)
### Complete Engineering & Deployment Setup Guide (macOS, Raspberry Pi 4B & Docker)

[![Powered by cl0ud](https://img.shields.io/badge/Powered%20by-cl0ud-00E5FF?style=for-the-badge&logoColor=0B0F19&labelColor=0B0F19)](https://github.com/Ojas-sta/cl0ud-brand-engineering)
[![Co-engineered by Ojas Singh](https://img.shields.io/badge/Co--engineered%20by-Ojas%20Singh-1E3A8A?style=for-the-badge&logoColor=white&labelColor=0B0F19)](https://github.com/Ojas-sta)
[![Upstream Source](https://img.shields.io/badge/Upstream-Thorn--probably%2Fadas-blue?style=for-the-badge&logo=github)](https://github.com/Thorn-probably/adas)
[![Docker ARM64](https://img.shields.io/badge/Docker-ARM64%20RPi4B-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

---

## 📋 Table of Contents
1. [Subsystem Overview](#1-subsystem-overview)
2. [Hardware Wiring Diagram (Raspberry Pi 4B)](#2-hardware-wiring-diagram-raspberry-pi-4b)
3. [macOS Development Setup](#3-macos-development-setup)
4. [Raspberry Pi 4B Native Setup](#4-raspberry-pi-4b-native-setup)
5. [Docker Containerization Deployment](#5-docker-containerization-deployment)
6. [Interactive Keyboard Controls](#6-interactive-keyboard-controls)
7. [Automated Verification & Unit Tests](#7-automated-verification--unit-tests)
8. [Engineering Attribution & Credits](#8-engineering-attribution--credits)

---

## 1. Subsystem Overview

The **ADAS Driver Monitoring System (DMS)** is an ultra-lean, ocular-focused computer vision engine designed specifically to deliver **35+ FPS on Raspberry Pi 4B (<20% CPU)**.

### Detection Mechanism
* **Perspective-Invariant Eye Tracking:** Utilizes MediaPipe's **3D Neural Blendshapes** (`eyeBlinkLeft`, `eyeBlinkRight`) extracted directly from the canonical 3D mesh. Eyelid closure remains accurate regardless of head yaw, pitch, or tilt.
* **Framerate-Agnostic PERCLOS:** Calculates percentage of eye closure over a rolling 4.0-second time window (35% threshold triggers drowsiness warning).
* **Neural Yawn Accumulation:** Measures sustained `jawOpen` ($>0.55$) for $\ge 0.7\text{s}$ to reject speech/singing while accumulating yawns over rolling 90 seconds.
* **Microsleep Emergency Alarm:** Eyes closed continuously for $\ge 1.2\text{s}$ triggers critical high-priority buzzer alarm.
* **Driver Slump / Unresponsive:** Loss of face detection for $\ge 2.0\text{s}$ triggers emergency alert.

---

## 2. Hardware Wiring Diagram (Raspberry Pi 4B)

Connect a standard 5V active buzzer directly to the Raspberry Pi 4B 40-pin GPIO header:

```
                      Raspberry Pi 4B 40-Pin Header
                               +---------+
                  3.3V  (Pin 1) | o     o | (Pin 2)  5V Power
                        (Pin 3) | o     o | (Pin 4)  5V Power
                        (Pin 5) | o     o | (Pin 6)  GND
                        (Pin 7) | o     o | (Pin 8)
                        (Pin 9) | o     o | (Pin 10)
                        (Pin 11)| o     o | (Pin 12) GPIO 18 (PWM0) ----> Active Buzzer (+) [Red]
                   GND  (Pin 14)| o     o | (Pin 14) GND --------> Active Buzzer (-) [Black]
                               +---------+
```

* **Signal Wire:** GPIO Pin 18 (Physical Pin 12) $\rightarrow$ Buzzer Positive (`+`)
* **Ground Wire:** Ground (Physical Pin 14 or Pin 6) $\rightarrow$ Buzzer Ground (`-`)

---

## 3. macOS Development Setup

Develop and verify the computer vision pipeline on macOS (Apple Silicon M1/M2/M3/M4/M5 or Intel) using the FaceTime HD camera, external USB webcams, or pre-recorded driving videos.

### 3.1 Prerequisites
* macOS 12+ (Monterey, Ventura, Sonoma, Sequoia)
* Python 3.10, 3.11, 3.12, or 3.13

### 3.2 Installation
```bash
# Clone the repository
git clone https://github.com/Ojas-sta/adas.git
cd adas

# Create and activate Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 3.3 Running on macOS
```bash
# 1. Run live GUI with built-in FaceTime HD camera
python main.py

# 2. Run with external USB camera (device index 1)
python main.py --camera 1

# 3. Run algorithm verification on test video (bundled test video)
python main.py --video test_videos/test_eyes_closed.mp4

# 4. Run headless performance benchmark
python main.py --video test_videos/test_normal.mp4 --headless
```

---

## 4. Raspberry Pi 4B Native Setup

Engineered for **Raspberry Pi OS 64-bit (Debian 12 Bookworm)**.

### 4.1 System Configuration
```bash
# Update OS packages
sudo apt update && sudo apt upgrade -y

# Enable Raspberry Pi Camera interface (if using CSI ribbon cable)
sudo raspi-config
# Navigate to: Interface Options -> Camera -> Enable -> Finish -> Reboot

# Ensure user has access to video, audio, and GPIO without sudo
sudo usermod -aG video,audio,gpio,dialout $USER
```

### 4.2 Install Runtime Dependencies
```bash
cd adas
python3 -m venv venv --system-site-packages
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

### 4.3 Execution Commands for Low-End Embedded Hardware

```bash
# 1. Standard Production Mode (320x240, 35+ FPS on Pi 4B)
python main.py --width 320 --height 240

# 2. In-Vehicle Headless Mode with Hardware GPIO 18 Buzzer (~15% CPU load)
python main.py --headless --gpio-buzzer --width 320 --height 240

# 3. Using native Raspberry Pi Camera Module (CSI ribbon cable via Picamera2)
python main.py --camera-type picamera2 --headless --gpio-buzzer --width 320 --height 240
```

---

## 5. Docker Containerization Deployment

The system is fully containerized with **offline model baking** (`face_landmarker.task` is embedded into `/app/models/` during `docker build`, requiring zero internet connectivity in vehicles).

### 5.1 Build the Docker Image
```bash
# Build native ARM64 image directly on Raspberry Pi 4B
docker build -t adas-rpi:latest .

# Or cross-compile from macOS/PC using Docker Buildx
docker buildx build --platform linux/arm64 -t adas-rpi:latest --load .
```

### 5.2 Run with Docker Compose

#### A. In-Vehicle Headless Mode (Production Vehicle Setup)
Starts automatically on boot (`restart: unless-stopped`), passes `/dev/video0`, `/dev/gpiomem`, and `/dev/snd`:
```bash
docker compose up -d adas-headless
```

#### B. Cockpit HUD GUI Mode (HDMI Display / Touchscreen)
Forward X11 display socket to render the live HUD overlay:
```bash
# Authorize local X11 socket access
xhost +local:root

# Launch GUI container
docker compose up adas-gui
```

#### C. Native CSI Camera Mode (Picamera2)
```bash
docker compose up -d adas-picam
```

#### D. Offline Simulation Mode (Test with bundled video)
```bash
docker compose up adas-simulation
```

### 5.3 Standalone Docker Run Command
```bash
docker run -d \
  --name adas_dms \
  --restart unless-stopped \
  --device /dev/video0:/dev/video0 \
  --device /dev/gpiomem:/dev/gpiomem \
  --device /dev/snd:/dev/snd \
  --group-add video \
  --group-add audio \
  --group-add gpio \
  adas-rpi:latest
```

---

## 6. Interactive Keyboard Controls

When running in GUI mode:

| Key | Action | Function |
| :---: | :--- | :--- |
| **`M`** | **Mute / Unmute** | Toggles audible warning beeps without terminating detection |
| **`Q`** or **`ESC`** | **Clean Quit** | Safely shuts down camera, audio dispatcher, and GPIO pins |

---

## 7. Automated Verification & Unit Tests

The test suite validates configuration defaults, MediaPipe blendshape extraction, framerate-agnostic PERCLOS math, non-blocking audio queueing, and HUD layout rendering.

```bash
# Run test suite
pytest tests/ -v
```

---

## 8. Engineering Attribution & Credits

<div align="center">
  <a href="https://github.com/Ojas-sta/cl0ud-brand-engineering">
    <img src="https://raw.githubusercontent.com/Ojas-sta/cl0ud-brand-engineering/main/assets/badges/cl0ud-credit-card.svg" alt="Powered by cl0ud | Co-engineered by Ojas Singh" width="100%" style="max-width: 820px;" />
  </a>
</div>

* **Original Upstream Author & Engine Design:** [Thorn-probably](https://github.com/Thorn-probably) ([Thorn-probably/adas](https://github.com/Thorn-probably/adas))
* **Systems Architecture & Containerization:** Powered by **[cl0ud](https://github.com/Ojas-sta/cl0ud-brand-engineering)** (founded by Ojas Singh)
* **Co-Engineered by:** **[Ojas Singh](https://github.com/Ojas-sta)** (`ojasctc@gmail.com`)
