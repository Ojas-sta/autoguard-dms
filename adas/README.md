# Automotive ADAS Driver Monitoring System (DMS)
### Specialized Eye Tracking & Drowsiness / Sleep Detection
**Engineered for Raspberry Pi 4B (ARM Cortex-A72) & Desktop**

[![Powered by cl0ud](https://img.shields.io/badge/Powered%20by-cl0ud-00E5FF?style=for-the-badge&logoColor=0B0F19&labelColor=0B0F19)](https://github.com/Ojas-sta/cl0ud-brand-engineering)
[![Co-engineered by Ojas Singh](https://img.shields.io/badge/Co--engineered%20by-Ojas%20Singh-1E3A8A?style=for-the-badge&logoColor=white&labelColor=0B0F19)](https://github.com/Ojas-sta)
[![Upstream Source](https://img.shields.io/badge/Upstream-Thorn--probably%2Fadas-blue?style=for-the-badge&logo=github)](https://github.com/Thorn-probably/adas)
[![Docker ARM64](https://img.shields.io/badge/Docker-ARM64%20RPi4B-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

A lightweight, real-time Computer Vision Driver Monitoring System (DMS) built to run at **35+ FPS on a Raspberry Pi 4B (<20% CPU)** using a single driver-facing camera, containerized with production-grade Docker and Docker Compose.

---

## 🚗 Core Focus: Eye State & Drowsiness

The system focuses exclusively on reliable, perspective-invariant ocular tracking and physiological drowsiness detection:

| Metric | Mechanism | Automotive Action |
| :--- | :--- | :--- |
| **Eye Openness Tracking** | Google MediaPipe Neural Blendshapes (`eyeBlinkLeft`, `eyeBlinkRight`) | Live continuous measurement from `0.0` (closed) to `1.0` (wide open). Invariant to head tilts and angles. |
| **Eye State Classification** | Thresholded eyelid closure ($>0.50$) with elapsed duration | `EYES: OPEN` vs `EYES: CLOSED (Xs)` status badge. |
| **Fatigue / PERCLOS** | Percentage of Eye Closure over rolling 4.0-second time window ($35\%$ threshold) | Framerate-agnostic detection of heavy eyelids and prolonged blink duration. |
| **Yawn Accumulator** | Neural `jawOpen` ($>0.55$) sustained $\ge 0.7\text{s}$ over rolling 90s | Distinguishes yawning from talking/singing. Warns on cumulative yawns. |
| **Microsleep Alarm** | Continuous eye closure for $\ge 1.2\text{s}$ | **CRITICAL: WAKE UP! MICROSLEEP DETECTED** audio/buzzer alarm. |
| **Driver Unresponsive / Slump** | Loss of face detection for $\ge 2.0\text{s}$ | **WARNING: DRIVER UNRESPONSIVE / FACE LOST** emergency alert. |

---

## ⚡ Why MediaPipe Neural Blendshapes for Embedded Devices?

Traditional Eye Aspect Ratio (EAR) using Euclidean pixel distances fails whenever the driver tilts their head or looks at an angle because 2D perspective foreshortening artificially squashes eye height, triggering constant false alarms.

This engine utilizes MediaPipe's **3D Face Blendshapes**, which extract normalized anatomical muscle activations directly from the 3D canonical mesh. Eyelid closure is measured accurately whether looking straight, turning, or tilting.

---

## 🎯 How the Low-End Device Mode Works (RPi 4B)

The system achieves **35+ FPS on Raspberry Pi 4B CPU** through 5 key architectural decisions:

1. **Pure Ocular Focus:** By decoupling heavy 6-DOF matrix math and complex 468-point mesh rendering, memory access overhead is eliminated.
2. **ARM-Optimized Resolution (`320x240`):** Feeding 320x240 frames into MediaPipe TFLite with XNNPACK NEON SIMD vectorization keeps inference latency under **9.5 ms** per frame.
3. **Headless In-Vehicle Operation:** Running with `--headless` skips X11 and Qt GUI buffer synchronization, dropping CPU consumption down to **~15%**.
4. **Hardware GPIO Buzzer (Pin 18):** Directly interfaces with `/dev/gpiomem` to trigger an active 5V buzzer without passing audio through the Linux sound subsystem.
5. **Offline Model Baking:** `face_landmarker.task` is embedded directly into the container image, allowing instantaneous boot in zero-connectivity vehicles.

### Low-End Device Native CLI Commands
```bash
# Recommended for Raspberry Pi 4B (320x240, 35+ FPS)
python main.py --width 320 --height 240

# Using native Raspberry Pi Camera Module (CSI ribbon cable via Picamera2)
python main.py --camera-type picamera2 --width 320 --height 240

# Headless in-vehicle deployment with hardware GPIO 18 active buzzer (~15% CPU)
python main.py --headless --gpio-buzzer --width 320 --height 240
```

---

## 🐳 Docker Deployment for Raspberry Pi 4B (`linux/arm64`)

The containerization is engineered for **Raspberry Pi OS 64-bit (Bookworm)** and modern automotive Linux kernels.

### 1. Build the Docker Image on Raspberry Pi
```bash
# Build native ARM64 image directly on Raspberry Pi 4B
docker build -t adas-rpi:latest .

# Or cross-compile from Mac/PC using Buildx
docker buildx build --platform linux/arm64 -t adas-rpi:latest --load .
```

### 2. Run with Docker Compose

#### Production In-Vehicle Mode (Headless + GPIO Buzzer + USB Camera)
```bash
docker compose up adas-headless
```
* Mounts `/dev/video0`, `/dev/gpiomem`, and `/dev/snd`.
* Auto-restarts on system boot (`unless-stopped`).
* Enforces 1GB RAM memory limit and 2 CPU cores.

#### Interactive GUI Mode (HDMI Monitor / Pi Touchscreen)
```bash
# Enable X11 socket access
xhost +local:root

# Start GUI container
docker compose up adas-gui
```

#### Native Pi Camera CSI Mode (Picamera2)
```bash
docker compose up adas-picam
```

#### Offline Simulation Mode (Test with bundled video)
```bash
docker compose up adas-simulation
```

### 3. Pure Docker Run Commands (Without Compose)
```bash
# In-vehicle headless mode
docker run -d \
  --name adas_dms \
  --restart unless-stopped \
  --device /dev/video0:/dev/video0 \
  --device /dev/gpiomem:/dev/gpiomem \
  --device /dev/snd:/dev/snd \
  adas-rpi:latest

# Desktop test mode with video
docker run --rm -it \
  adas-rpi:latest python main.py --video /app/test_videos/test_eyes_closed.mp4 --headless
```

---

## 🔌 Hardware Wiring Diagram (GPIO 18 Buzzer)

Connect a 5V active buzzer directly to the Raspberry Pi 4B 40-pin GPIO header:

```
Raspberry Pi 4B Header:
Pin 12 (GPIO 18 / PWM0) ------> Buzzer (+) Positive / Signal
Pin 14 (GND)            ------> Buzzer (-) Ground
```

---

## 🎮 Interactive Controls (GUI Mode)

| Key | Action | Description |
| :---: | :--- | :--- |
| **`M`** | **Mute / Unmute** | Toggles audible warning beeps |
| **`Q` / `ESC`** | **Quit** | Closes camera feed and cleanly exits |

---

## 🤝 Engineering Attribution & Credits

<div align="center">
  <a href="https://github.com/Ojas-sta/cl0ud-brand-engineering">
    <img src="https://raw.githubusercontent.com/Ojas-sta/cl0ud-brand-engineering/main/assets/badges/cl0ud-credit-card.svg" alt="Powered by cl0ud | Co-engineered by Ojas Singh" width="100%" style="max-width: 820px;" />
  </a>
</div>

This project is a collaborative automotive engineering effort:

* **Original Upstream Author & Engine Design:** [Thorn-probably](https://github.com/Thorn-probably) — author of the specialized eye-tracking & drowsiness detection ADAS engine ([Thorn-probably/adas](https://github.com/Thorn-probably/adas)).
* **Systems Architecture & Containerization:** Powered by **[cl0ud](https://github.com/Ojas-sta/cl0ud-brand-engineering)** (founded by Ojas Singh).
* **Co-Engineered by:** **[Ojas Singh](https://github.com/Ojas-sta)** (`ojasctc@gmail.com`).

---

## 📄 License
Distributed under the MIT License. See [LICENSE](LICENSE) for details.
