"""
==============================================================================
Subsystem: ADAS Unit & Regression Test Suite
Upstream Reference: https://github.com/Thorn-probably/adas
Architecture: Powered by cl0ud (https://github.com/Ojas-sta/cl0ud-brand-engineering)
Co-Engineered by: Ojas Singh <ojasctc@gmail.com>
==============================================================================
"""

import os
import sys
import time
import pytest
import numpy as np
import cv2

# Add adas directory to path
ADAS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADAS_DIR not in sys.path:
    sys.path.insert(0, ADAS_DIR)

from config import DMSConfig
from dms_engine import DMSEngine, DMSFrameResult
from hud_overlay import DMSHUDOverlay
from audio_alert import AudioAlertManager


def test_dms_config_defaults():
    config = DMSConfig()
    assert config.FRAME_WIDTH == 320
    assert config.FRAME_HEIGHT == 240
    assert config.TARGET_FPS == 30
    assert config.BLINK_CLOSED_THRESHOLD == 0.50
    assert config.MICROSLEEP_DURATION_SEC == 1.2
    assert config.PERCLOS_WINDOW_SEC == 4.0
    assert config.FACE_LOST_TIMEOUT_SEC == 2.0


def test_dms_engine_initialization():
    config = DMSConfig()
    engine = DMSEngine(config)
    assert engine.face_landmarker is not None
    assert engine.frame_idx == 0


def test_dms_engine_custom_model_fallback():
    config = DMSConfig()
    config.ENGINE_TYPE = "custom"
    # Even if torch is not installed or torchscript model is used, engine initializes cleanly
    engine = DMSEngine(config)
    blank_frame = np.zeros((240, 320, 3), dtype=np.uint8)
    res = engine.process_frame(blank_frame)
    assert res is not None
    assert isinstance(res, DMSFrameResult)


def test_dms_engine_no_face():
    config = DMSConfig()
    engine = DMSEngine(config)
    blank_frame = np.zeros((240, 320, 3), dtype=np.uint8)
    
    res = engine.process_frame(blank_frame)
    assert res.face_detected is False
    assert res.drowsiness_state in ("SEARCHING", "UNRESPONSIVE")


def test_dms_engine_video_processing():
    video_path = os.path.join(ADAS_DIR, "test_videos", "test_eyes_closed.mp4")
    assert os.path.exists(video_path), f"Video missing at {video_path}"
    
    cap = cv2.VideoCapture(video_path)
    assert cap.isOpened()
    
    config = DMSConfig()
    engine = DMSEngine(config)
    
    frames_processed = 0
    face_detected_count = 0
    
    for _ in range(15):
        ret, frame = cap.read()
        if not ret:
            break
        frame_resized = cv2.resize(frame, (320, 240))
        res = engine.process_frame(frame_resized)
        frames_processed += 1
        if res.face_detected:
            face_detected_count += 1
            
    cap.release()
    assert frames_processed == 15
    assert face_detected_count > 0, "Should detect face in test video"


def test_hud_overlay_rendering():
    config = DMSConfig()
    hud = DMSHUDOverlay(config)
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    
    # Test Alert State
    res_alert = DMSFrameResult(face_detected=True, eye_openness=0.85, drowsiness_state="ALERT")
    out_alert = hud.render(frame, res_alert, fps=35.0, sound_enabled=True)
    assert out_alert.shape == (240, 320, 3)
    
    # Test Microsleep Alarm State
    res_microsleep = DMSFrameResult(
        face_detected=True,
        is_eye_closed=True,
        eye_closed_duration=1.5,
        drowsiness_state="MICROSLEEP",
        active_alarms=["MICROSLEEP"]
    )
    out_sleep = hud.render(frame, res_microsleep, fps=30.0, sound_enabled=False)
    assert out_sleep.shape == (240, 320, 3)


def test_hud_overlay_compact_badge_layout():
    # Verify that at 320x240, badges do not crash and render within bounds
    config = DMSConfig()
    config.FRAME_WIDTH = 320
    config.FRAME_HEIGHT = 240
    hud = DMSHUDOverlay(config)
    frame = np.zeros((240, 320, 3), dtype=np.uint8)

    res_unresp = DMSFrameResult(face_detected=False, face_lost_duration=3.5, drowsiness_state="UNRESPONSIVE", active_alarms=["UNRESPONSIVE"])
    rendered = hud.render(frame, res_unresp, fps=35.0, sound_enabled=True)
    assert rendered.shape == (240, 320, 3)


def test_audio_alert_manager():
    audio = AudioAlertManager(enabled=True, min_interval=0.1, enable_gpio=False)
    try:
        audio.trigger("MICROSLEEP")
        audio.trigger("DROWSY")
        audio.trigger("UNRESPONSIVE")
        audio.set_enabled(False)
        assert audio.enabled is False
    finally:
        audio.stop()
