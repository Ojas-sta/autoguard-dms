"""
Guided Gaze Calibration Manager for Driver Monitoring System.
Guides the driver through 6 calibration targets (Road, Left Mirror, Right Mirror, Down, Up, Away),
collects empirical iris and head kinematics samples, and computes personalized classification boundaries.
"""

from dataclasses import dataclass, asdict
import json
import logging
import os
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class GazeCalibrationProfile:
    """Personalized calibration boundaries and neutral offsets."""
    road_yaw_min: float = -14.0
    road_yaw_max: float = 14.0
    road_pitch_min: float = -12.0
    road_pitch_max: float = 14.0
    left_mirror_yaw: float = -20.0
    right_mirror_yaw: float = 20.0
    down_console_pitch: float = 15.0
    up_ceiling_pitch: float = -15.0
    iris_neutral_x: float = 0.50
    iris_neutral_y: float = 0.50
    calibration_timestamp: float = 0.0
    is_calibrated: bool = False


class GazeCalibrationManager:
    """Manages multi-target guided calibration and profile persistence."""

    TARGET_STEPS = [
        ("ROAD", "Look straight ahead at the road"),
        ("LEFT_MIRROR", "Look left towards the side mirror"),
        ("RIGHT_MIRROR", "Look right towards the passenger mirror"),
        ("DOWN", "Look down towards the instrument cluster / console"),
        ("UP", "Look upwards towards the rear-view / sun visor"),
        ("AWAY", "Look outside the driving zone")
    ]

    def __init__(self, profile_path: Optional[str] = None):
        if profile_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            profile_path = os.path.join(base_dir, "profiles", "gaze_calibration.json")

        self._profile_path = profile_path
        self._profile = GazeCalibrationProfile()
        self._is_active = False
        self._current_step_idx = 0
        self._samples_for_step: List[Tuple[float, float, float, float]] = []  # (iris_x, iris_y, pitch, yaw)
        self._target_samples_per_step = 20
        self._step_data: Dict[str, List[Tuple[float, float, float, float]]] = {}

        self.load_profile()

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def current_step_name(self) -> str:
        if not self._is_active or self._current_step_idx >= len(self.TARGET_STEPS):
            return "IDLE"
        return self.TARGET_STEPS[self._current_step_idx][0]

    @property
    def current_step_instruction(self) -> str:
        if not self._is_active or self._current_step_idx >= len(self.TARGET_STEPS):
            return "Ready"
        return self.TARGET_STEPS[self._current_step_idx][1]

    @property
    def step_progress(self) -> float:
        if not self._is_active:
            return 1.0
        return len(self._samples_for_step) / float(self._target_samples_per_step)

    @property
    def total_progress(self) -> float:
        if not self._is_active:
            return 1.0
        completed = self._current_step_idx * self._target_samples_per_step + len(self._samples_for_step)
        total = len(self.TARGET_STEPS) * self._target_samples_per_step
        return completed / float(total)

    def start_calibration(self) -> None:
        """Starts the interactive guided calibration sequence."""
        self._is_active = True
        self._current_step_idx = 0
        self._samples_for_step.clear()
        self._step_data.clear()
        logger.info("Interactive gaze calibration started: Step 1/%d (%s)", len(self.TARGET_STEPS), self.current_step_name)

    def cancel_calibration(self) -> None:
        self._is_active = False
        self._samples_for_step.clear()
        self._step_data.clear()
        logger.info("Gaze calibration cancelled.")

    def record_sample(self, iris_x: float, iris_y: float, pitch: float, yaw: float) -> bool:
        """
        Records a frame observation during active calibration.
        Returns True when entire calibration is complete.
        """
        if not self._is_active:
            return False

        self._samples_for_step.append((iris_x, iris_y, pitch, yaw))

        if len(self._samples_for_step) >= self._target_samples_per_step:
            step_name = self.current_step_name
            self._step_data[step_name] = list(self._samples_for_step)
            self._samples_for_step.clear()
            self._current_step_idx += 1

            if self._current_step_idx >= len(self.TARGET_STEPS):
                # Completed all steps!
                self._compute_and_save_profile()
                self._is_active = False
                logger.info("Gaze calibration successfully completed and saved!")
                return True
            else:
                logger.info("Gaze calibration advancing to Step %d/%d (%s)", self._current_step_idx + 1, len(self.TARGET_STEPS), self.current_step_name)

        return False

    def _compute_and_save_profile(self) -> None:
        """Calculates boundary limits from empirical target distributions."""
        road_samples = self._step_data.get("ROAD", [])
        left_samples = self._step_data.get("LEFT_MIRROR", [])
        right_samples = self._step_data.get("RIGHT_MIRROR", [])
        down_samples = self._step_data.get("DOWN", [])
        up_samples = self._step_data.get("UP", [])

        if road_samples:
            road_pitches = [s[2] for s in road_samples]
            road_yaws = [s[3] for s in road_samples]
            road_iris_x = [s[0] for s in road_samples]
            road_iris_y = [s[1] for s in road_samples]

            mean_y = sum(road_yaws) / len(road_yaws)
            mean_p = sum(road_pitches) / len(road_pitches)

            self._profile.road_yaw_min = round(mean_y - 12.0, 1)
            self._profile.road_yaw_max = round(mean_y + 12.0, 1)
            self._profile.road_pitch_min = round(mean_p - 11.0, 1)
            self._profile.road_pitch_max = round(mean_p + 12.0, 1)
            self._profile.iris_neutral_x = round(sum(road_iris_x) / len(road_iris_x), 3)
            self._profile.iris_neutral_y = round(sum(road_iris_y) / len(road_iris_y), 3)

        if left_samples:
            left_yaws = [s[3] for s in left_samples]
            self._profile.left_mirror_yaw = round(sum(left_yaws) / len(left_yaws), 1)

        if right_samples:
            right_yaws = [s[3] for s in right_samples]
            self._profile.right_mirror_yaw = round(sum(right_yaws) / len(right_yaws), 1)

        if down_samples:
            down_pitches = [s[2] for s in down_samples]
            self._profile.down_console_pitch = round(sum(down_pitches) / len(down_pitches), 1)

        if up_samples:
            up_pitches = [s[2] for s in up_samples]
            self._profile.up_ceiling_pitch = round(sum(up_pitches) / len(up_pitches), 1)

        self._profile.calibration_timestamp = time.time()
        self._profile.is_calibrated = True

        self.save_profile()

    def save_profile(self) -> None:
        """Saves calibration profile to JSON file."""
        os.makedirs(os.path.dirname(os.path.abspath(self._profile_path)), exist_ok=True)
        try:
            with open(self._profile_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self._profile), f, indent=2)
            logger.info("Saved gaze calibration profile to %s", self._profile_path)
        except Exception as e:
            logger.error("Failed saving gaze calibration profile: %s", e)

    def load_profile(self) -> GazeCalibrationProfile:
        """Loads calibration profile from JSON file if present."""
        if os.path.exists(self._profile_path):
            try:
                with open(self._profile_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in data.items():
                    if hasattr(self._profile, k):
                        setattr(self._profile, k, v)
                logger.info("Loaded existing gaze calibration profile from %s", self._profile_path)
            except Exception as e:
                logger.warning("Error reading calibration profile: %s", e)
        return self._profile

    # Aliases
    load_calibration = load_profile
    save_calibration = save_profile

    @property
    def profile(self) -> GazeCalibrationProfile:
        return self._profile
