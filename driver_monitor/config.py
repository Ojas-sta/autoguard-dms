"""
Configuration module for the Driver Monitoring System (DMS).
Defines operational thresholds, timing intervals, hardware settings, and profile defaults.
"""

from dataclasses import dataclass, field
import json
import os
from typing import Any, Dict


@dataclass
class EyeMonitoringConfig:
    ear_closed_threshold: float = 0.22       # Below this EAR is considered CLOSED
    ear_open_threshold: float = 0.27         # Above this EAR is considered OPEN
    blink_min_duration_sec: float = 0.08     # Minimum duration of a valid blink
    blink_max_duration_sec: float = 0.40     # Maximum duration of a normal blink
    closure_attention_sec: float = 0.8       # Sustained closure triggering ATTENTION
    closure_warning_sec: float = 1.5         # Sustained closure triggering DROWSINESS_WARNING
    closure_critical_sec: float = 2.5        # Sustained closure triggering CRITICAL_DEMO_ALERT
    blink_rate_window_sec: float = 60.0      # Rolling window for calculating blink rate
    low_blink_rate_threshold: float = 6.0    # Abnormally low blinks per min
    high_blink_rate_threshold: float = 35.0  # Abnormally high blinks per min (flutter)
    perclos_window_sec: float = 60.0         # Rolling window for PERCLOS calculation
    perclos_warning_threshold: float = 0.15  # 15% eye closure over window
    perclos_critical_threshold: float = 0.30 # 30% eye closure over window


@dataclass
class HeadPoseConfig:
    # Thresholds in degrees
    pitch_down_threshold: float = -18.0      # Head nodding down threshold
    pitch_up_threshold: float = 22.0         # Head looking up
    yaw_turned_threshold: float = 28.0       # Looking left or right (> |yaw|)
    roll_tilted_threshold: float = 22.0      # Sustained head tilt (> |roll|)
    
    # Timing in seconds
    head_down_attention_sec: float = 1.2     # Attention trigger
    head_down_warning_sec: float = 2.2       # Warning trigger
    head_turned_attention_sec: float = 1.8   # Driver looking away attention
    head_turned_warning_sec: float = 3.0     # Driver looking away warning
    head_tilted_warning_sec: float = 2.5     # Abnormal tilt warning
    
    # Nodding detection
    nod_pitch_dip: float = 12.0              # Pitch change magnitude for a nod
    nod_time_window_sec: float = 3.5         # Window to detect repeated nods
    nod_count_warning: int = 2               # Number of nods in window to warn


@dataclass
class YawningConfig:
    mar_open_threshold: float = 0.55         # Mouth Aspect Ratio for open mouth
    yawn_min_duration_sec: float = 1.6       # Sustained open mouth for a yawn (vs talking)
    yawn_max_duration_sec: float = 7.0       # Maximum valid single yawn duration
    speech_max_duration_sec: float = 0.8     # Speech mouth opening rarely exceeds 0.8s
    yawn_cooldown_sec: float = 3.0           # Minimum interval between consecutive yawns
    yawn_count_warning_window_sec: float = 180.0  # 3 minute window
    yawn_count_warning: int = 3              # 3 yawns in window triggers attention/warning


@dataclass
class AbnormalMovementConfig:
    erratic_jerk_threshold: float = 85.0     # Angular velocity change deg/s^2
    unusual_movement_window_sec: float = 4.0
    face_lost_attention_sec: float = 2.0     # Face loss attention
    face_lost_warning_sec: float = 4.0       # Face loss warning (distraction / out of frame)
    slump_pitch_threshold: float = -28.0     # Sudden head slump
    slump_motionless_sec: float = 2.5        # Slumped and motionless


@dataclass
class CameraConfig:
    default_device_index: int = 0
    resolution_width: int = 1280
    resolution_height: int = 720
    target_fps: int = 30
    backend: str = "AVFOUNDATION"            # AVFOUNDATION, OPENCV, PICAMERA2, V4L2
    warmup_frames: int = 5


@dataclass
class HardwareConfig:
    platform_name: str = "macos"
    simulation_mode: bool = True
    buzzer_enabled: bool = True
    led_enabled: bool = True
    buzzer_volume: float = 0.8
    # Pi GPIO pin mappings (ignored on macOS)
    gpio_buzzer_pin: int = 18
    gpio_led_green_pin: int = 23
    gpio_led_yellow_pin: int = 24
    gpio_led_orange_pin: int = 25
    gpio_led_red_pin: int = 12
    gpio_emergency_button_pin: int = 16


@dataclass
class AppConfig:
    platform: str = "macos"
    eye: EyeMonitoringConfig = field(default_factory=EyeMonitoringConfig)
    head_pose: HeadPoseConfig = field(default_factory=HeadPoseConfig)
    yawning: YawningConfig = field(default_factory=YawningConfig)
    abnormal: AbnormalMovementConfig = field(default_factory=AbnormalMovementConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    hardware: HardwareConfig = field(default_factory=HardwareConfig)
    debug_mode: bool = False
    log_level: str = "INFO"

    @classmethod
    def from_profile(cls, profile_path: str) -> "AppConfig":
        """Loads configuration overrides from a JSON profile file."""
        config = cls()
        if not os.path.exists(profile_path):
            return config

        try:
            with open(profile_path, "r") as f:
                data = json.load(f)

            if "platform" in data:
                config.platform = data["platform"]
            if "camera" in data:
                for k, v in data["camera"].items():
                    if hasattr(config.camera, k):
                        setattr(config.camera, k, v)
            if "hardware" in data:
                for k, v in data["hardware"].items():
                    if hasattr(config.hardware, k):
                        setattr(config.hardware, k, v)
            if "eye" in data:
                for k, v in data["eye"].items():
                    if hasattr(config.eye, k):
                        setattr(config.eye, k, v)
            if "head_pose" in data:
                for k, v in data["head_pose"].items():
                    if hasattr(config.head_pose, k):
                        setattr(config.head_pose, k, v)
        except Exception as e:
            print(f"Error loading profile {profile_path}: {e}")

        return config
