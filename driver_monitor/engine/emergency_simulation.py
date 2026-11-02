"""
Emergency Simulation and Scenario Injection Engine.
Allows manual triggering of emergency states and synthetic behavioral simulations
for testing, demonstration, and automated verification without physical driver actions.
"""

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class EmergencySimulationEngine:
    """Manages manual emergency triggers and simulated behavioral test injections."""

    def __init__(self):
        self._manual_emergency_active = False
        self._emergency_trigger_time = 0.0

        # Simulation override states
        self._simulate_drowsiness = False
        self._drowsiness_sim_start = 0.0

        self._simulate_abnormal_movement = False
        self._abnormal_sim_start = 0.0

        self._simulate_face_lost = False
        self._face_lost_sim_start = 0.0

    def trigger_emergency(self) -> None:
        """Manually activates highest-priority emergency state."""
        self._manual_emergency_active = True
        self._emergency_trigger_time = time.time()
        logger.warning("MANUAL EMERGENCY TRIGGERED by driver / operator")

    def reset_emergency(self) -> None:
        """Clears manual emergency state and all simulations."""
        self._manual_emergency_active = False
        self._simulate_drowsiness = False
        self._simulate_abnormal_movement = False
        self._simulate_face_lost = False
        logger.info("Emergency state and simulations reset to NORMAL")

    def toggle_emergency(self) -> bool:
        if self._manual_emergency_active:
            self.reset_emergency()
        else:
            self.trigger_emergency()
        return self._manual_emergency_active

    def toggle_simulate_drowsiness(self) -> bool:
        self._simulate_drowsiness = not self._simulate_drowsiness
        if self._simulate_drowsiness:
            self._drowsiness_sim_start = time.time()
            logger.info("Drowsiness simulation STARTED")
        else:
            logger.info("Drowsiness simulation STOPPED")
        return self._simulate_drowsiness

    def toggle_simulate_abnormal_movement(self) -> bool:
        self._simulate_abnormal_movement = not self._simulate_abnormal_movement
        if self._simulate_abnormal_movement:
            self._abnormal_sim_start = time.time()
            logger.info("Abnormal movement simulation STARTED")
        else:
            logger.info("Abnormal movement simulation STOPPED")
        return self._simulate_abnormal_movement

    def toggle_simulate_face_lost(self) -> bool:
        self._simulate_face_lost = not self._simulate_face_lost
        if self._simulate_face_lost:
            self._face_lost_sim_start = time.time()
            logger.info("Face loss simulation STARTED")
        else:
            logger.info("Face loss simulation STOPPED")
        return self._simulate_face_lost

    @property
    def is_emergency_active(self) -> bool:
        return self._manual_emergency_active

    @property
    def is_drowsiness_simulated(self) -> bool:
        return self._simulate_drowsiness

    @property
    def is_abnormal_movement_simulated(self) -> bool:
        return self._simulate_abnormal_movement

    @property
    def is_face_lost_simulated(self) -> bool:
        return self._simulate_face_lost

    def get_drowsiness_sim_duration(self) -> float:
        if self._simulate_drowsiness:
            return time.time() - self._drowsiness_sim_start
        return 0.0

    def get_abnormal_sim_duration(self) -> float:
        if self._simulate_abnormal_movement:
            return time.time() - self._abnormal_sim_start
        return 0.0
