"""
Result Models and Data Structures for Driver Monitoring System.
Shared data contracts between detection modules, decision engines, hardware layer, and UI.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple
import numpy as np


class EyeStatus(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"


class DrowsinessState(Enum):
    NORMAL = "NORMAL"
    ATTENTION = "ATTENTION"
    DROWSINESS_WARNING = "DROWSINESS_WARNING"
    CRITICAL_DEMO_ALERT = "CRITICAL_DEMO_ALERT"


class AbnormalMovementState(Enum):
    NORMAL = "NORMAL"
    ABNORMAL_HEAD_POSTURE = "ABNORMAL_HEAD_POSTURE"
    UNUSUAL_HEAD_MOVEMENT = "UNUSUAL_HEAD_MOVEMENT"
    DRIVER_ATTENTION_LOST = "DRIVER_ATTENTION_LOST"
    POSSIBLE_DRIVER_EMERGENCY_DEMO = "POSSIBLE_DRIVER_EMERGENCY_DEMO"


class AlertLevel(Enum):
    NORMAL = "NORMAL"
    ATTENTION = "ATTENTION"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class EyeMetrics:
    left_ear: float = 0.0
    right_ear: float = 0.0
    avg_ear: float = 0.0
    left_status: EyeStatus = EyeStatus.UNKNOWN
    right_status: EyeStatus = EyeStatus.UNKNOWN
    overall_status: EyeStatus = EyeStatus.UNKNOWN
    closure_duration_sec: float = 0.0
    blink_count: int = 0
    blink_frequency_bpm: float = 0.0
    is_prolonged_closure: bool = False
    raw_left_landmarks: List[Tuple[float, float]] = field(default_factory=list)
    raw_right_landmarks: List[Tuple[float, float]] = field(default_factory=list)


@dataclass
class HeadPoseMetrics:
    pitch: float = 0.0  # degrees (+ = up, - = down)
    yaw: float = 0.0    # degrees (+ = right, - = left)
    roll: float = 0.0   # degrees (+ = tilt right, - = tilt left)
    is_head_down: bool = False
    is_head_turned: bool = False
    is_head_tilted: bool = False
    head_down_duration_sec: float = 0.0
    head_turned_duration_sec: float = 0.0
    head_tilted_duration_sec: float = 0.0
    head_nod_count: int = 0
    recent_nod_detected: bool = False
    rotation_vector: Optional[np.ndarray] = None
    translation_vector: Optional[np.ndarray] = None
    projected_axes: Optional[List[Tuple[int, int]]] = None


@dataclass
class MouthMetrics:
    mar: float = 0.0
    is_mouth_open: bool = False
    is_yawning: bool = False
    yawn_duration_sec: float = 0.0
    yawn_count: int = 0
    recent_yawn_detected: bool = False
    raw_mouth_landmarks: List[Tuple[float, float]] = field(default_factory=list)


@dataclass
class FaceDetectionResult:
    detected: bool = False
    confidence: float = 0.0
    bbox: Tuple[int, int, int, int] = (0, 0, 0, 0)  # (x, y, w, h)
    landmarks_2d: List[Tuple[float, float]] = field(default_factory=list)
    landmarks_3d: List[Tuple[float, float, float]] = field(default_factory=list)
    face_lost_duration_sec: float = 0.0
    tracking_id: int = 0


@dataclass
class DrowsinessResult:
    state: DrowsinessState = DrowsinessState.NORMAL
    score: float = 0.0  # 0.0 (fully alert) to 1.0 (asleep)
    reasons: List[str] = field(default_factory=list)
    perclos: float = 0.0  # Percentage of eye closure time over rolling window


@dataclass
class AbnormalMovementResult:
    state: AbnormalMovementState = AbnormalMovementState.NORMAL
    alert_title: str = ""
    details: str = ""
    is_active: bool = False


@dataclass
class SystemAlert:
    level: AlertLevel = AlertLevel.NORMAL
    title: str = "SYSTEM READY"
    description: str = "Driver alert and attentive"
    color_code: str = "#10b981"  # green
    buzzer_active: bool = False
    buzzer_pattern: str = "OFF"  # OFF, CHIME, DOUBLE_PULSE, RAPID_SIREN
    led_green: bool = True
    led_yellow: bool = False
    led_orange: bool = False
    led_red: bool = False
    is_emergency: bool = False
    timestamp: float = 0.0


@dataclass
class PerformanceMetrics:
    fps: float = 0.0
    processing_latency_ms: float = 0.0
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    resolution: Tuple[int, int] = (0, 0)
    source_type: str = "webcam"
    source_name: str = "Default"


@dataclass
class FrameAnalysisResult:
    timestamp: float = 0.0
    frame_index: int = 0
    face: FaceDetectionResult = field(default_factory=FaceDetectionResult)
    eyes: EyeMetrics = field(default_factory=EyeMetrics)
    head_pose: HeadPoseMetrics = field(default_factory=HeadPoseMetrics)
    mouth: MouthMetrics = field(default_factory=MouthMetrics)
    drowsiness: DrowsinessResult = field(default_factory=DrowsinessResult)
    abnormal: AbnormalMovementResult = field(default_factory=AbnormalMovementResult)
    alert: SystemAlert = field(default_factory=SystemAlert)
    performance: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    annotated_frame: Optional[np.ndarray] = None
