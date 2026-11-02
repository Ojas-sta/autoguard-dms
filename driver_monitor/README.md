# AutoGuard Driver Monitoring System (DMS)
### Standalone Driver Drowsiness, Dizziness & Attention Detection Module (macOS Development & Raspberry Pi Deployment)

![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Raspberry%20Pi-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-brightgreen.svg)
![Tests](https://img.shields.io/badge/Unit%20Tests-33%2F33%20Passing-success.svg)
![Status](https://img.shields.io/badge/Build-Passing-brightgreen.svg)

---

## 1. Executive Summary & Objective

The **AutoGuard Driver Monitoring System (DMS)** is a production-grade, standalone computer vision system that monitors driver attentiveness, fatigue, drowsiness, and abnormal kinematics.

This macOS development version enables developers and engineers to **run, develop, calibrate, and test the exact computer vision and decision algorithms on Apple Silicon (M1/M2/M3/M4/M5) and Intel Macs** using the MacBook built-in FaceTime HD camera, external USB webcams, or prerecorded test videos before deploying to a physical Raspberry Pi 4B.

### Key Architectural Principle: Zero Algorithm Duplication
The computer vision models, landmark extractors, Eye Aspect Ratio (EAR), Mouth Aspect Ratio (MAR), 3D head pose estimation, drowsiness multi-signal fusion, and alert decision logic are **100% shared** across macOS and Raspberry Pi. Only camera drivers, GPIO outputs, and audio player adapters differ via a clean Hardware Abstraction Layer (HAL).

```
                      +------------------------------------+
                      |     SHARED DETECTION ALGORITHMS    |
                      |  * Face Landmark Tracking (468 pts)|
                      |  * Eye Aspect Ratio (EAR) & Blinks |
                      |  * 3D Head Pose (Pitch, Yaw, Roll) |
                      |  * Mouth Aspect Ratio & Yawning    |
                      |  * Drowsiness Multi-Signal Engine  |
                      |  * Abnormal Movement / Dizziness   |
                      |  * Priority Alert Decision Engine  |
                      +-----------------+------------------+
                                        |
                 +----------------------+----------------------+
                 |                                             |
                 v                                             v
    +-------------------------+                   +-------------------------+
    |   macOS Profile (HAL)   |                   | Raspberry Pi 4B (HAL)   |
    | * AVFoundation Webcam   |                   | * Picamera2 / V4L2      |
    | * afplay Audio Tones    |                   | * Physical GPIO Buzzer  |
    | * Virtual Cockpit LEDs  |                   | * Physical GPIO LEDs    |
    | * Native PyQt6 Cockpit  |                   | * Headless / Pi Display |
    +-------------------------+                   +-------------------------+
```

---

## 2. Real Detection Algorithms

### A. Face Detection & Landmark Tracking
* **Framework:** MediaPipe Tasks FaceLandmarker (3D mesh with 468+ points).
* **Hardware Acceleration:** Native Metal GPU delegation & XNNPACK on Apple Silicon.
* **Bounding Box Stabilization:** Exponential Moving Average (EMA) bounding box smoothing prevents display jitter.
* **Confidence & Face Loss:** Real-time confidence score and tracking of face unavailability duration.

### B. Eye Monitoring & EAR Analysis
* **Metric:** Eye Aspect Ratio ($EAR$) based on Soukupová and Čech:
  $$EAR = \frac{||p_2 - p_6|| + ||p_3 - p_5||}{2 \times ||p_1 - p_4||}$$
* **Eye State:** Hysteresis thresholding ($EAR < 0.22 \rightarrow \text{CLOSED}$, $EAR > 0.27 \rightarrow \text{OPEN}$).
* **Closure Duration:** Tracks continuous closure time with millisecond precision.
* **Blink Analytics:** Classifies natural blinks ($80\text{ms} \le \text{duration} \le 400\text{ms}$) and maintains rolling blink frequency (Blinks per Minute over 60s).
* **PERCLOS:** Computes percentage of eye closure time over a rolling 60-second window.

### C. 3D Head Pose Estimation (SolvePnP)
* **Kinematics:** Projects 3D anthropometric face model against 2D landmark coordinates using `cv2.solvePnP` and `cv2.RQDecomp3x3`.
* **Angles:**
  * **Pitch:** Head up / down ($< -18^\circ$ indicates head droop).
  * **Yaw:** Head left / right ($> |28^\circ|$ indicates looking away).
  * **Roll:** Head tilt sideways ($> |22^\circ|$ indicates head tilt).
* **Nodding Detection:** Tracks rapid downward pitch dips ($> 12^\circ$) followed by rebound recovery (microsleep rebound signature).
* **3D Axes Projection:** Renders 3D coordinate axes (Red = Roll, Green = Pitch, Blue = Yaw) directly projected onto the driver's nose.
* **Interactive Zeroing:** "Zero Head Pose" button calibrates any camera placement as forward-looking neutral.

### D. Yawning Detection (Speech-Filtered)
* **Metric:** Mouth Aspect Ratio ($MAR$):
  $$MAR = \frac{||p_{13} - p_{14}|| + ||p_{81} - p_{178}|| + ||p_{311} - p_{402}||}{3 \times ||p_{78} - p_{308}||}$$
* **Speech Immunity:** Rejects brief conversational syllables ($< 0.8\text{s}$). Only flags sustained mouth opening ($> 1.6\text{s}$) with $MAR \ge 0.55$.
* **Yawn Frequency:** Tracks yawn count and duration over a 3-minute rolling window.

### E. Drowsiness Decision Engine
Fuses multiple indicators into four standard automotive states:
1. **NORMAL:** Eyes open, normal blink frequency, level head pose.
2. **ATTENTION:** Isolated yawn, early eye closure ($0.8\text{s} - 1.5\text{s}$), or head beginning to droop.
3. **DROWSINESS_WARNING:** Prolonged eye closure ($1.5\text{s} - 2.5\text{s}$), sustained head-down ($> 2.2\text{s}$), or repeated nodding.
4. **CRITICAL_DEMO_ALERT:** Severe eye closure ($> 2.5\text{s}$), microsleep nod with eyes closed, or high PERCLOS ($> 30\%$).

### F. Abnormal Head Movement & Dizziness Indicators (Non-Diagnostic)
* **Disclaimer:** Experimental behavioral indicators only. Not a medical diagnostic device.
* **Descriptive Alerts:**
  * *Abnormal Head Posture:* Sustained head tilt sideways ($> 22^\circ$ for $> 2.5\text{s}$).
  * *Unusual Head Movement:* Erratic movement or high angular jerk ($> 85^\circ/\text{s}$).
  * *Driver Attention Lost:* Head turned away ($> 28^\circ$ for $> 3.0\text{s}$) or face missing from frame ($> 4.0\text{s}$).
  * *Possible Driver Emergency – Demo:* Sudden head slump ($< -28^\circ$) sustained and motionless.

---

## 3. macOS Hardware Simulation Layer

| Raspberry Pi 4B Physical | macOS Simulation Implementation | Behavior |
|---|---|---|
| **Piezo Buzzer (GPIO 18)** | Native macOS `/usr/bin/afplay` | Plays synthesized multi-tone WAV alerts (Chime, Double Pulse, Rapid Siren, Emergency) in non-blocking threads. |
| **LED Cluster (GPIO 23, 24, 25, 12)** | Virtual Cockpit LED Indicators | Green (Norm), Yellow (Attn), Orange (Warn), Red (Crit) render with specular highlights and glowing effects. |
| **Emergency Push Button (GPIO 16)** | Software Button & Hazard Hotkey | Triggers highest priority Critical Emergency alert and audible siren. |
| **Picamera2 / Pi Camera V1** | macOS AVFoundation (`cv2.CAP_AVFOUNDATION`) | 1080p/720p 30 FPS camera capture with automatic device enumeration. |
| **Display** | High-performance Native PyQt6 Window | Cockpit dashboard running at 60 FPS without GIL blocking. |

---

## 4. Desktop Cockpit UI

The application features an automotive dark dashboard designed for driver monitoring:
* **Live Camera View:** Displays bounding box, eye landmarks, mouth contours, 3D pose vector, and top HUD bar.
* **Biometric Telemetry Cards:** Real-time numerical readouts and progress bars for EAR, MAR, Blink Rate, Closure Duration, and Yawn Count.
* **Kinematics Readout:** Pitch, Yaw, Roll angles with status tags (`LEVEL`, `HEAD DOWN`, `TURNED`, `TILTED`).
* **Real-time Strip Charts:** Rolling 120-frame graphs for EAR trend, MAR trend, and Head Orientation angles with threshold lines.
* **System Diagnostics:** Live FPS, processing latency (ms), CPU usage, and Memory usage.
* **Interactive Control Bar:**
  * *Start / Stop Monitoring*
  * *Camera Selection:* Dropdown listing built-in and external USB cameras.
  * *Test Video Selector:* One-click loading of preset scenario videos.
  * *Audio Mute Toggle:* Enable/disable sound alarms.
  * *Simulate Drowsy:* Injects synthetic drowsiness without physical driver strain.
  * *Simulate Abnormal Head:* Injects synthetic head tilt and erratic movement.
  * *Trigger Emergency & Reset Alerts:* Simulates emergency conditions.

---

## 5. Repository Structure

```
driver_monitor/
│
├── main.py                     # Entry point with CLI flags (--platform, --video, --camera, --headless)
├── config.py                   # Dataclass configurations & profile loader
├── requirements.txt            # Dependency definitions
├── setup.sh                    # Automated setup script
├── README.md                   # Complete documentation
│
├── core/
│   ├── platform_manager.py     # OS & CPU architecture detector (macOS vs Pi)
│   ├── detection_pipeline.py   # Master frame-by-frame processing pipeline
│   ├── result_models.py        # Shared data contracts, enums & results
│   └── event_manager.py        # Thread-safe pub/sub event bus
│
├── camera/
│   ├── camera_interface.py     # Abstract CameraInterface base class
│   ├── camera_manager.py       # Camera switcher & runtime coordinator
│   ├── mac_camera.py           # macOS AVFoundation camera implementation
│   ├── pi_camera.py            # Raspberry Pi Picamera2 / V4L2 implementation
│   └── video_source.py         # Prerecorded video player (pause, seek, restart)
│
├── detection/
│   ├── face_detection.py       # MediaPipe Face Landmarker & bounding box smoother
│   ├── eye_detection.py        # EAR math, blink counter, closure tracker
│   ├── head_pose.py            # solvePnP 3D pose, Euler angles, nod detector
│   ├── yawning_detection.py    # MAR calculation & speech-filtered yawn detector
│   └── behavior_analysis.py    # Rolling PERCLOS & angular jerk dynamics
│
├── engine/
│   ├── drowsiness_engine.py    # Multi-signal fatigue state machine
│   ├── abnormal_movement_engine.py # Non-diagnostic movement & posture engine
│   ├── alert_manager.py        # Priority arbitration, buzzer patterns, LED states
│   └── emergency_simulation.py # Manual triggers & test scenario injector
│
├── hardware/
│   ├── interfaces.py           # BuzzerInterface, LEDInterface, EmergencyButtonInterface
│   ├── hardware_factory.py     # Factory instantiating Mac or Pi hardware layer
│   ├── macos/
│   │   ├── mac_buzzer.py       # afplay audio player
│   │   ├── mac_led.py          # Virtual dashboard LED cluster
│   │   └── mac_emergency_button.py # Software emergency trigger
│   └── raspberrypi/
│       ├── gpio_buzzer.py      # Pi GPIO buzzer (with mock fallback on Mac)
│       ├── gpio_led.py         # Pi GPIO LEDs (with mock fallback on Mac)
│       └── gpio_emergency_button.py # Pi GPIO button (with mock fallback on Mac)
│
├── dashboard/
│   ├── main_window.py          # Master cockpit GUI with background QThread worker
│   ├── camera_widget.py        # Video viewport & scrub bar
│   ├── monitoring_panel.py     # Biometric telemetry cards
│   ├── performance_panel.py    # Diagnostics (FPS, latency, CPU, memory)
│   ├── debug_panel.py          # Real-time QPainter rolling strip charts
│   └── alert_widget.py         # Alert banner & hardware LED cluster
│
├── logging/
│   └── event_logger.py         # Structured event logger (dms_events.log)
│
├── models/
│   ├── download_models.py      # Automated model asset retriever
│   └── face_landmarker.task    # Pre-trained MediaPipe model asset (3.7MB)
│
├── resources/
│   ├── sounds/                 # Synthesized WAV audio alert files
│   └── videos/                 # Procedurally generated MP4 scenario videos
│
├── profiles/
│   ├── macos.json              # macOS profile configuration
│   └── raspberrypi.json        # Raspberry Pi profile configuration
│
├── utils/
│   ├── audio_generator.py      # Pure-Python wave synthesizer for alert tones
│   └── video_generator.py      # Deterministic procedural MP4 test video generator
│
└── tests/
    ├── test_eye_detection.py
    ├── test_head_pose.py
    ├── test_yawning_detection.py
    ├── test_drowsiness_engine.py
    ├── test_abnormal_movement.py
    ├── test_alert_manager.py
    └── test_integration_scenarios.py
```

---

## 6. Installation & Execution on macOS

### Prerequisites
* macOS 13 (Ventura), 14 (Sonoma), 15 (Sequoia) or newer.
* Apple Silicon Mac (M1/M2/M3/M4/M5) or Intel Mac.
* Python 3.10, 3.11, 3.12, or 3.13.

### Automated One-Command Setup
Run the automated setup script to set up a virtual environment, install dependencies, download models, synthesize sound assets, generate test videos, and run the test suite:

```bash
chmod +x setup.sh
./setup.sh
```

### Manual Setup Step-by-Step

1. **Create and Activate Virtual Environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install Dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Verify Model Assets:**
   ```bash
   python -m driver_monitor.models.download_models
   ```

4. **Generate Audio & Video Test Suite:**
   ```bash
   python -m driver_monitor.utils.audio_generator
   python -m driver_monitor.utils.video_generator
   ```

5. **Run the Application on macOS:**
   ```bash
   # Launch using MacBook FaceTime Camera
   python main.py --platform macos

   # Or run with a prerecorded test video
   python main.py --video driver_monitor/resources/videos/test_eyes_closed.mp4

   # Or run headless verification benchmark
   python main.py --headless --frames 120
   ```

---

## 7. macOS Camera Permissions Instructions

When accessing the camera for the first time, macOS AVFoundation requires camera access permission.

If the camera feed shows a black frame or "CAMERA STANDBY":
1. Open **System Settings** on your Mac.
2. Navigate to **Privacy & Security $\rightarrow$ Camera**.
3. Ensure that your terminal application (e.g. **Terminal**, **iTerm2**, or **VS Code**) has the toggle switch **ON**.
4. If prompted with *"Terminal would like to access the camera"*, click **OK**.

---

## 8. Test Video Verification & The 16 Scenarios

The suite includes built-in procedural test videos in `driver_monitor/resources/videos/` covering all required scenarios:

| # | Scenario | Verification Method | Expected Result |
|---|---|---|---|
| **1** | Face detected normally | `test_normal.mp4` | Face bounding box drawn, confidence $>85\%$, Status `NORMAL`. |
| **2** | Face not detected | `test_face_lost.mp4` | Face lost timer increments; bounding box cleared. |
| **3** | Eyes open | `test_normal.mp4` | $EAR > 0.27$, Eye Status = `OPEN`. |
| **4** | Eyes closed | `test_eyes_closed.mp4` | $EAR < 0.22$, Eye Status = `CLOSED`. |
| **5** | Prolonged eye closure | `test_eyes_closed.mp4` | At $1.5\text{s} \rightarrow$ `DROWSINESS_WARNING`; at $2.5\text{s} \rightarrow$ `CRITICAL_DEMO_ALERT`. |
| **6** | Repeated blinking | `test_normal.mp4` | Blinks detected ($80-400\text{ms}$), Blink Rate updated in bpm. |
| **7** | Head tilted | `test_head_tilted.mp4` | Roll angle $> 22^\circ \rightarrow$ Alert: `Abnormal Head Posture`. |
| **8** | Head nodding | `test_head_nodding.mp4` | Pitch oscillation detected $\rightarrow$ Nodding counter increments. |
| **9** | Head turned left/right | `test_head_turned.mp4` | Yaw angle $> 28^\circ \rightarrow$ Alert: `Driver Attention Lost`. |
| **10**| Yawning | `test_yawning.mp4` | $MAR \ge 0.55$ sustained $> 1.6\text{s} \rightarrow$ Status: `YAWNING`. |
| **11**| Face temporarily unavailable | `test_face_lost.mp4` | Missing $> 4.0\text{s} \rightarrow$ Alert: `Driver Attention Lost`. |
| **12**| Manual emergency trigger | GUI "Trigger Emergency" Button | Immediate `CRITICAL` alert, Red LED lit, Siren audio sounds. |
| **13**| Reset emergency alert | GUI "Reset Alerts" Button | Reverts state to `NORMAL`, stops buzzer, Green LED lit. |
| **14**| Camera disconnected | Zero-frame test case | Graceful handling without exceptions or pipeline crash. |
| **15**| Video-file playback | Any MP4 file | Full scrub bar, seek, pause, resume, loop functionality. |
| **16**| Camera switching | GUI Camera combo box | Runtime hot-swap between webcam and video files. |

---

## 9. Running the Automated Test Suite

Run the full automated unit test suite with:

```bash
python -m unittest discover -s driver_monitor/tests -v
```

### Test Results Summary:
* Total Tests: **33 passed, 0 failed, 0 errors**
* Coverage:
  * `test_eye_detection.py` (EAR, Open/Closed, Blink rate, Prolonged closure)
  * `test_head_pose.py` (SolvePnP, Euler angles, Nodding, Tilt, Turn)
  * `test_yawning_detection.py` (MAR, Speech rejection, Sustained yawn)
  * `test_drowsiness_engine.py` (State escalation, Hysteresis, Microsleeps)
  * `test_abnormal_movement.py` (Postures, Erratic jerk, Slump, Face lost)
  * `test_alert_manager.py` (Priority arbitration, Mute, LED/Buzzer patterns)
  * `test_integration_scenarios.py` (Camera switching, Video playback, Seeking)

---

## 10. Raspberry Pi 4B Deployment Profile

When transferring the project to a Raspberry Pi 4B:

1. **Hardware Connections:**
   * Active Piezo Buzzer: GPIO 18 (Pin 12) + GND (Pin 14)
   * Green LED (Normal): GPIO 23 (Pin 16) + $330\Omega$ resistor
   * Yellow LED (Attention): GPIO 24 (Pin 18) + $330\Omega$ resistor
   * Orange LED (Warning): GPIO 25 (Pin 22) + $330\Omega$ resistor
   * Red LED (Critical): GPIO 12 (Pin 32) + $330\Omega$ resistor
   * Emergency Push Button: GPIO 16 (Pin 36) + GND (Pin 34) (Internal pull-up enabled)
   * Camera: Raspberry Pi Camera Module V1/V2/V3 connected to CSI port.

2. **Execution on Raspberry Pi:**
   ```bash
   python main.py --platform raspberrypi
   ```
   The application automatically engages `GPIOBuzzer`, `GPIOLED`, and `Picamera2` while executing the identical shared computer vision models without changing a single line of detection code.
