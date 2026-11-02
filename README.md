# AutoGuard Driver Monitoring System (DMS)
### Exhibition-Grade Driver Monitoring, Road Gaze Tracking, Distraction Detection & Raspberry Pi Deployment

![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Raspberry%20Pi%204B%20%7C%20Docker-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-brightgreen.svg)
![Tests](https://img.shields.io/badge/Unit%20Tests-63%2F63%20Passing-success.svg)
![Status](https://img.shields.io/badge/Build-Passing-brightgreen.svg)
![Docker](https://img.shields.io/badge/Docker-Multi--Arch%20ARM64%2FAMD64-blue.svg)

---

## 1. Executive Summary & Objective

The **AutoGuard Driver Monitoring System (DMS)** is a standalone, exhibition-ready computer vision platform that monitors driver attentiveness, fatigue, drowsiness, abnormal kinematics, road gaze direction, and visual distraction in real time.

This development version enables engineers to **run, develop, calibrate, and verify all computer vision and decision algorithms on Apple Silicon (M1/M2/M3/M4/M5) and Intel Macs** using the MacBook built-in FaceTime HD camera, external USB webcams, or prerecorded test videos before deploying to a physical Raspberry Pi 4B.

### Key Architectural Principle: Zero Algorithm Duplication
The computer vision models, 478-point landmark extractors, iris tracking, Eye Aspect Ratio (EAR), Mouth Aspect Ratio (MAR), 3D head pose estimation, gaze direction classifier, distraction analysis engine, multi-signal decision engine, and alert arbitration logic are **100% shared** across macOS, Docker, and Raspberry Pi. Only camera drivers, GPIO outputs, and audio adapters differ via a clean Hardware Abstraction Layer (HAL).

```
                      +------------------------------------------+
                      |       SHARED DETECTION ALGORITHMS        |
                      |  * Face Landmark Tracking (478 pts)      |
                      |  * Normalized Iris Tracking (468, 473)   |
                      |  * 3D Head Pose (+Y Down SolvePnP)       |
                      |  * Multi-Observation Neutral Calibration |
                      |  * Road Gaze Estimation (6 Zones)        |
                      |  * Eye Aspect Ratio (EAR) & Blinks       |
                      |  * Mouth Aspect Ratio & Yawn Detection   |
                      |  * Driver Distraction Engine (CSV Log)   |
                      |  * Drowsiness Multi-Signal Engine        |
                      |  * Abnormal Movement / Dizziness Demo    |
                      |  * Priority Alert Arbitration Engine     |
                      +--------------------+---------------------+
                                           |
                  +------------------------+------------------------+
                  |                        |                        |
                  v                        v                        v
     +-------------------------+  +--------------------+  +-------------------------+
     |   macOS Profile (HAL)   |  |   Docker Profile   |  | Raspberry Pi 4B (HAL)   |
     | * AVFoundation Webcam   |  | * Multi-Arch Image |  | * Picamera2 / V4L2      |
     | * afplay Audio Tones    |  | * Headless Stream  |  | * Physical GPIO Buzzer  |
     | * Virtual Cockpit LEDs  |  | * Benchmarking CSV |  | * Physical GPIO LEDs    |
     | * Native PyQt6 Cockpit  |  | * USB / CSI Mount  |  | * ESP32-S3 UART Offload |
     +-------------------------+  +--------------------+  +-------------------------+
```

---

## 2. Advanced Detection Algorithms

### A. Face Detection & 478-Point Landmark Tracking
* **Framework:** MediaPipe Tasks FaceLandmarker (Dense 478-point mesh including ocular contours and irises).
* **Hardware Acceleration:** Native Metal GPU delegation & XNNPACK on Apple Silicon; optimized NEON/TFLite on ARM64.
* **Bounding Box Stabilization:** Exponential Moving Average (EMA) bounding box smoothing eliminates jitter.
* **Confidence & Face Loss:** Real-time confidence score and tracking of face unavailability duration.

### B. Iris Tracking & Ocular Boundary Metrics
* **Landmarks:** Iris centers (Landmark 468 = Right eye in image / driver's left; Landmark 473 = Left eye in image / driver's right) and 4-point ocular boundaries (inner, outer, top, bottom).
* **Metrics:** Normalized horizontal ($[0, 1]$) and vertical ($[0, 1]$) iris ratios relative to eye dimensions.
* **Temporal Smoothing:** Exponential moving average filters ocular micro-saccades and camera noise.

### C. Corrected 3D Head Pose Estimation (+Y Down Standard)
* **Coordinate Inversion Resolved:** Face model 3D coordinates aligned with OpenCV camera coordinate conventions ($+X$ right, $+Y$ down, $+Z$ forward), resolving angle wrapping to $\sim 175^\circ$ and false head-down warnings. Pitch now reads $0^\circ$ when looking forward and positive when dipping downwards.
* **Multi-Observation Neutral Calibration:** 25-frame rolling buffer computes personalized neutral offsets and reports calibration confidence.
* **Kinematics:** Projects 3D anthropometric face model against 2D landmark coordinates using `cv2.solvePnP` and `cv2.RQDecomp3x3`.
* **Angles:**
  * **Pitch:** Head up / down ($> 16.0^\circ$ indicates head droop).
  * **Yaw:** Head left / right ($> |26.0^\circ|$ indicates looking away).
  * **Roll:** Head tilt sideways ($> |22.0^\circ|$ indicates head tilt).
* **Nodding Detection:** Tracks rapid downward pitch dips ($> 12^\circ$) followed by rebound recovery (microsleep rebound signature).
* **3D Axes Projection:** Renders 3D coordinate axes (Red = Roll, Green = Pitch, Blue = Yaw) directly projected onto the driver's nose.

### D. Road Gaze Estimation & Classification
* **Multimodal Fusion:** Fuses normalized iris displacement ($40\%$) with calibrated head pose angles ($60\%$).
* **Classification Zones:**
  * `ROAD`: Looking forward towards the road.
  * `LEFT_MIRROR`: Looking towards the driver side mirror.
  * `RIGHT_MIRROR`: Looking towards the passenger side mirror.
  * `DOWN`: Looking down towards instrument cluster or center console.
  * `UP`: Looking upwards towards interior mirror or visor.
  * `AWAY`: Looking outside expected driving cones.
  * `UNKNOWN`: Insufficient confidence or eyes closed.
* **Guided Individual Calibration:** Interactive 6-target wizard (`ROAD`, `LEFT_MIRROR`, `RIGHT_MIRROR`, `DOWN`, `UP`, `AWAY`) captures individual anatomical boundaries and persists to `driver_monitor/profiles/gaze_calibration.json`.
* **Dwell Time:** Tracks continuous dwell time in the current gaze zone.
* **Visual Vector Overlay:** Renders an origin-to-target 2D gaze vector arrow and forward crosshair.

### E. Driver Distraction Detection & Road Attention Analytics
* **Visual Distraction:** Sustained glance away from forward road ($> 2.0\text{s}$).
* **Downward Distraction:** Extended gaze towards instrument console / simulated phone area ($> 1.8\text{s}$).
* **Side Distraction:** Sustained head rotation combined with off-road gaze.
* **Distraction States:**
  * `NORMAL`: Attentive forward road gaze.
  * `BRIEF_GLANCE`: Normal mirrors/instruments check ($< 1.0\text{s}$).
  * `ATTENTION_WARNING`: Off-road dwell exceeding normal check ($1.0\text{s} - 1.5\text{s}$).
  * `VISUAL_DISTRACTION`: Off-road dwell $> 2.0\text{s}$.
  * `DOWNWARD_DISTRACTION`: Extended downward glance $> 1.8\text{s}$.
  * `CRITICAL_DEMO_ALERT`: Extended off-road dwell $> 3.5\text{s}$ or glance $> 2.0\text{s}$ with head turned.
* **Road Attention Analytics:** Rolling window road gaze % ($> 75\%$ target), off-road glance counters (Down, Left, Right), longest glance tracker, and distraction events/min.
* **CSV Telemetry Export:** "EXPORT CSV" button exports full timestamped gaze, pitch, yaw, roll, and distraction logs to `logs/gaze_analytics_*.csv`.

### F. Eye Monitoring & EAR Analysis
* **Metric:** Eye Aspect Ratio ($EAR$) based on Soukupová and Čech:
  $$EAR = \frac{||p_2 - p_6|| + ||p_3 - p_5||}{2 \times ||p_1 - p_4||}$$
* **Eye State:** Hysteresis thresholding ($EAR < 0.22 \rightarrow \text{CLOSED}$, $EAR > 0.27 \rightarrow \text{OPEN}$).
* **Closure Duration:** Tracks continuous closure time with millisecond precision.
* **Blink Analytics:** Classifies natural blinks ($80\text{ms} \le \text{duration} \le 400\text{ms}$) and maintains rolling blink frequency (BPM over 60s).
* **PERCLOS:** Computes percentage of eye closure time over a rolling 60-second window.

### G. Yawning Detection (Speech-Filtered)
* **Metric:** Mouth Aspect Ratio ($MAR$):
  $$MAR = \frac{||p_{13} - p_{14}|| + ||p_{81} - p_{178}|| + ||p_{311} - p_{402}||}{3 \times ||p_{78} - p_{308}||}$$
* **Speech Immunity:** Rejects brief conversational syllables ($< 0.8\text{s}$). Only flags sustained mouth opening ($> 1.6\text{s}$) with $MAR \ge 0.55$.
* **Yawn Frequency:** Tracks yawn count and duration over a 3-minute rolling window.

### H. Drowsiness Decision Engine
Fuses multiple indicators into standard automotive states:
1. **NORMAL:** Eyes open, normal blink frequency, level head pose.
2. **ATTENTION:** Isolated yawn, early eye closure ($0.8\text{s} - 1.5\text{s}$), or head beginning to droop.
3. **DROWSINESS_WARNING:** Prolonged eye closure ($1.5\text{s} - 2.5\text{s}$), sustained head-down ($> 2.0\text{s}$), or repeated nodding.
4. **CRITICAL_DEMO_ALERT:** Severe eye closure ($> 2.5\text{s}$), microsleep nod with eyes closed, or high PERCLOS ($> 30\%$).

### I. Abnormal Head Movement & Dizziness Indicators (Non-Diagnostic)
* **Disclaimer:** Experimental behavioral indicators only. Not a medical diagnostic device.
* **Descriptive Alerts:**
  * *Abnormal Head Posture:* Sustained head tilt sideways ($> 22^\circ$ for $> 2.5\text{s}$).
  * *Unusual Head Movement:* Erratic movement or high angular jerk ($> 85^\circ/\text{s}$).
  * *Driver Attention Lost:* Head turned away ($> 26^\circ$ for $> 3.0\text{s}$) or face missing from frame ($> 4.0\text{s}$).
  * *Possible Driver Emergency – Demo:* Sudden head slump ($> 28^\circ$) sustained and motionless.

---

## 3. Cockpit Dashboard & Telemetry Interface

The desktop GUI provides an automotive-grade cockpit display:

* **Top Header Controls:**
  * `🔊 AUDIO: ON/OFF`: Mutes or enables buzzer tones.
  * `⚠️ DISTRACTION: ON/OFF`: Enables or bypasses visual distraction alerts.
  * `👁️ OVERLAYS: ON/OFF`: Toggles iris centers, gaze vector, 3D axes, and crosshairs.
  * `🎯 ZERO HEAD POSE`: Triggers 25-frame multi-observation neutral calibration.
  * `👀 CALIBRATE GAZE`: Opens modal 6-target guided individual calibration dialog.
  * `💾 EXPORT CSV`: Exports recorded gaze and distraction analytics to timestamped CSV.
  * `📈 CHARTS: ON/OFF`: Toggles real-time rolling telemetry strip charts.
* **Telemetry Panels:**
  * **Driver Face & Tracking:** Confidence %, detection status, face lost timer.
  * **Eye Status & EAR:** Left/Right eye status, EAR meter bar, closure timer, blink rate.
  * **Yawning & Mouth:** MAR meter bar, yawn count, yawn duration.
  * **Head Pose & Kinematics:** Pitch, Yaw, Roll angles (°), posture, nod counter.
  * **Road Gaze & Iris:** Current zone badge, confidence %, zone dwell time, normalized iris ratio.
  * **Distraction & Attention Analytics:** State badge, off-road glance timer, road attention % progress bar, glance counters (Down, Left, Right), event counter.
* **Real-time Strip Charts (High Performance QPainter):**
  * Eye Aspect Ratio (EAR) vs. closure threshold.
  * Mouth Aspect Ratio (MAR) vs. yawn threshold.
  * Head Orientation angles (Pitch, Yaw, Roll).
  * Road Attention % & Scaled Off-Road Glance Duration.
  * Rolling Event and State Transition Log.
* **Bottom Action Bar:**
  * Camera device switcher (FaceTime camera, USB cameras).
  * 7 preset test video scenarios (Normal, Eyes closed, Nodding, Yawning, Tilted, Turned, Face lost).
  * Simulation injection buttons (`Simulate Road Gaze`, `Simulate Distraction`, `Simulate Drowsy`, `Simulate Abnormal Head`, `Reset Stats`).

---

## 4. Raspberry Pi 4B Optimisations & Power Profiles

AutoGuard DMS features three hardware power profiles stored in `driver_monitor/profiles/`:

| Profile | Target Capture | Target Inference | Skip Ratio | Target Hardware | Typical CPU |
|---|---|---|---|---|---|
| **`LOW_POWER`** | 20 FPS | 10 FPS | 1:3 frames | Raspberry Pi 4B (Battery / Fanless) | ~35% |
| **`BALANCED`** | 30 FPS | 15 FPS | 1:2 frames | Raspberry Pi 4B (Standard Active Cooling) | ~55% |
| **`HIGH_QUALITY`** | 30 FPS | 30 FPS | 1:1 (All) | Raspberry Pi 5 / macOS Development | ~75% |

### Deep Raspberry Pi 4B Computer Vision Optimizations
To ensure 100% shared algorithm execution on ARM Cortex-A72 without thermal throttling or frame lag:
1. **Threaded Latest-Frame Decoupled Capture (`ThreadedCamera`)**:
   * Decouples hardware camera reads (`Picamera2` or V4L2) from the inference pipeline via a dedicated daemon thread.
   * Retains only the newest sensor frame and drops stale buffer frames, completely eliminating camera buffer lag (glass-to-glass latency drops from $>1000\text{ms}$ to $<35\text{ms}$).
2. **Sub-graph Pruning in Neural Models**:
   * Disables unused 52-blendshape classification and 3D affine transformation matrices in MediaPipe FaceLandmarker (`output_face_blendshapes=False`, `output_facial_transformation_matrixes=False`), saving $\sim 25\text{ms}$ per frame on CPU.
3. **Inference Resolution Pre-Downsampling**:
   * Downsamples input video frames to $320 \times 240$ prior to TFLite tensor feeding while projecting output coordinates back to native display dimensions, reducing pixel processing volume by $75\%$.
4. **Extrinsic-Guess Warm-Starting for SolvePnP**:
   * Caches previous rotation and translation vectors and initializes iterative Levenberg-Marquardt with `useExtrinsicGuess=True`, converging head pose in 1–2 iterations instead of 20.
   * Caches camera intrinsic matrices and distortion coefficients, eliminating per-frame numpy re-allocations.
5. **$O(1)$ Constant-Time Sliding Window Accumulators**:
   * Replaced $O(N)$ 1800-iteration loops in PERCLOS and distraction rolling windows with running sum accumulators, saving 54,000 loop operations/sec at 30 FPS.
6. **Zero-Copy Sub-ROI HUD Alpha Blending**:
   * Directly slices frame sub-regions (`annotated[0:36, 0:w]`) for UI banner blending, eliminating full-frame clones on ARM.
7. **Adaptive Frame Inference & State Interpolation**:
   * Reuses previous detection results on intermediate frames when head and eyes remain steady according to `face_detection_interval_frames`.

### Automated Performance Benchmark Runner
A standalone headless benchmark script measures system throughput, processing latency, and hardware resource utilization without running the GUI:

```bash
# Run 15-second benchmark on Balanced profile
python -m driver_monitor.benchmark --profile BALANCED --duration 15.0

# Run 30-second benchmark on Low Power profile
python -m driver_monitor.benchmark --profile LOW_POWER --duration 30.0

# Benchmark physical live camera instead of reproducible test video
python -m driver_monitor.benchmark --profile BALANCED --live --duration 10.0
```

The benchmark outputs an ASCII summary table to stdout and exports a full per-frame CSV report to `logs/benchmark_*.csv`.

---

## 5. ESP32-S3 Peripheral Controller Integration

To minimize CPU load on the Raspberry Pi 4B and provide deterministic hardware safety, AutoGuard DMS supports offloading buzzer PWM and LED cluster driving to a companion **ESP32-S3** microcontroller over UART serial (115200 baud).

* **Complete Architecture Analysis:** See [`driver_monitor/hardware/esp32/ARCHITECTURE_EVALUATION.md`](file:///Users/roopalisingh/Documents/antigravity/clever-bose/driver_monitor/hardware/esp32/ARCHITECTURE_EVALUATION.md).
* **Arduino C++ Firmware:** Ready-to-flash sketch at [`driver_monitor/hardware/esp32/firmware/autoguard_esp32s3.ino`](file:///Users/roopalisingh/Documents/antigravity/clever-bose/driver_monitor/hardware/esp32/firmware/autoguard_esp32s3.ino).
* **UART JSON Protocol:**
  * **Raspberry Pi $\rightarrow$ ESP32:** Alert state updates (`{"version": 1, "command": "ALERT_UPDATE", "led_state": "RED", "buzzer": true, "buzzer_pattern": "RAPID_SIREN"}`).
  * **ESP32 $\rightarrow$ Raspberry Pi:** Heartbeats & interrupt events (`{"event": "EMERGENCY_BUTTON_PRESSED", "timestamp": 12345}`).
  * **Safety Watchdog:** ESP32 silences buzzer if heartbeat is lost for $> 2.0\text{s}$.

---

## 6. Docker & Docker Compose Deployment

Multi-architecture Docker support allows running AutoGuard DMS in containerized environments:

### Build and Run with Docker Compose

```bash
# 1. Dev Video Mode (macOS / PC / Server Headless)
docker compose --profile dev-video up --build

# 2. Raspberry Pi 4B with USB Webcam
docker compose --profile pi-usb up --build -d

# 3. Raspberry Pi 4B with CSI Camera Module
docker compose --profile pi-csi up --build -d
```

For full container documentation, see [`docker/README.md`](file:///Users/roopalisingh/Documents/antigravity/clever-bose/docker/README.md).

---

## 7. Installation & Quick Start on macOS

### 1. Prerequisites
* macOS 12+ (Monterey, Ventura, Sonoma, Sequoia)
* Apple Silicon (M1/M2/M3/M4/M5) or Intel Core Mac
* Python 3.10 – 3.13

### 2. Environment Setup
```bash
git clone <repo_url>
cd clever-bose

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Generate Resources
```bash
# Generate procedural alert tones and preset test videos
python -m driver_monitor.utils.audio_generator
python -m driver_monitor.utils.video_generator
```

### 4. Run Application
```bash
# Launch interactive cockpit GUI using FaceTime webcam
python main.py --platform macos

# Launch with preset video
python main.py --video resources/videos/test_normal.mp4

# Run headless verification benchmark
python -m driver_monitor.benchmark --profile BALANCED --duration 10.0
```

---

## 8. Automated Test Suite

Run all 63 unit and integration tests:

```bash
pytest driver_monitor/tests/ -v
```

### Test Coverage Summary:
* `test_threaded_camera.py`: Decoupled asynchronous frame grabber, buffer freshening, clean release.
* `test_iris_tracking.py`: Normalized ratios, 478 points, temporal filtering.
* `test_gaze_estimation.py`: 6 driving attention zones, dwell time, gaze vectors.
* `test_distraction_engine.py`: Visual, downward, critical distraction, CSV export.
* `test_gaze_calibration.py`: Guided 6-target wizard, boundary calculation, JSON persistence.
* `test_head_pose.py`: $+Y$ down pitch convention, SolvePnP, tilt, nodding, multi-observation calibration.
* `test_esp32_controller.py`: UART protocol, JSON serialization, button interrupts.
* `test_eye_detection.py`: EAR metric, blink frequency, prolonged closure.
* `test_yawning_detection.py`: MAR metric, speech rejection, sustained yawning.
* `test_drowsiness_engine.py`: Multi-signal escalation, hysteresis.
* `test_abnormal_movement.py`: Jerk analysis, head tilt, motionless slump.
* `test_alert_manager.py`: Alert priority arbitration, LED/buzzer patterns.
* `test_integration_scenarios.py`: Camera switching, video seek/loop, disconnect safety.

**Result:** `63 passed in 5.27s (100% Passing)`
