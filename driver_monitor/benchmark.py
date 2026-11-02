"""
Performance Benchmark Runner for AutoGuard DMS.
Evaluates end-to-end computer vision throughput, inference latency, and hardware load
across different power profiles (LOW_POWER, BALANCED, HIGH_QUALITY, MAC_DEVELOPMENT).
Produces a structured CSV report and formatted console summary.

==============================================================================
Subsystem: Automated Performance Benchmarking & Resource Profiling
Architecture: Powered by cl0ud (https://github.com/Ojas-sta/cl0ud-brand-engineering)
Co-Engineered by: Ojas Singh <ojasctc@gmail.com>
==============================================================================
"""

import argparse
import csv
from datetime import datetime
import json
import logging
import os
import sys
import time
from typing import Dict, List, Optional
import cv2
import numpy as np
import psutil

# Ensure project root is on PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from driver_monitor.camera.camera_manager import CameraManager
from driver_monitor.config import AppConfig, RPiPowerConfig
from driver_monitor.core.detection_pipeline import DetectionPipeline
from driver_monitor.core.platform_manager import PlatformManager
from driver_monitor.hardware.interfaces import DummyBuzzer, DummyLED, DummyEmergencyButton
from driver_monitor.logging.event_logger import EventLogger
from driver_monitor.utils.video_generator import generate_test_video

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Benchmark")


def run_benchmark(
    profile_name: str = "BALANCED",
    duration_sec: float = 15.0,
    video_path: Optional[str] = None,
    camera_idx: int = 0,
    use_live_camera: bool = False,
    output_csv: Optional[str] = None
) -> Dict[str, float]:
    """Runs headless automated benchmark and records performance telemetry."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    profiles_dir = os.path.join(base_dir, "driver_monitor", "profiles")

    # Load configuration based on profile
    profile_file_map = {
        "LOW_POWER": "raspberrypi_low_power.json",
        "BALANCED": "raspberrypi_balanced.json",
        "HIGH_QUALITY": "raspberrypi_high_quality.json",
        "MAC_DEVELOPMENT": "macos.json"
    }

    config = AppConfig()
    filename = profile_file_map.get(profile_name.upper(), "raspberrypi_balanced.json")
    profile_path = os.path.join(profiles_dir, filename)

    if os.path.exists(profile_path):
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "camera" in data:
                    config.camera.resolution_width = data["camera"].get("resolution_width", 640)
                    config.camera.resolution_height = data["camera"].get("resolution_height", 480)
                    config.camera.target_fps = data["camera"].get("target_fps", 30)
                if "power" in data:
                    config.power = RPiPowerConfig(**data["power"])
            logger.info("Loaded profile settings from %s", profile_path)
        except Exception as e:
            logger.warning("Could not load profile JSON: %s. Using default config.", e)

    # Prepare dummy actuators
    buzzer = DummyBuzzer()
    leds = DummyLED()
    button = DummyEmergencyButton()
    event_logger = EventLogger()

    # Initialize Detection Pipeline
    pipeline = DetectionPipeline(config, buzzer, leds, button, event_logger)

    # Prepare Video Source
    cap = None
    is_live = False
    if video_path and os.path.exists(video_path):
        logger.info("Using prerecorded benchmark video: %s", video_path)
        cap = cv2.VideoCapture(video_path)
    elif use_live_camera:
        test_cap = cv2.VideoCapture(camera_idx)
        if test_cap.isOpened():
            ret, _ = test_cap.read()
            if ret:
                cap = test_cap
                is_live = True
                logger.info("Using physical camera device index: %d", camera_idx)
            else:
                test_cap.release()

    if cap is None:
        # Check standard preset test videos first for reproducible benchmarks
        preset_paths = [
            os.path.join(base_dir, "driver_monitor", "resources", "videos", "test_normal.mp4"),
            os.path.join(base_dir, "resources", "videos", "test_normal.mp4"),
        ]
        for p in preset_paths:
            if os.path.exists(p):
                cap = cv2.VideoCapture(p)
                logger.info("Using standard benchmark test video: %s", p)
                break

    if cap is None:
        # Fallback: generate synthetic test video
        synth_dir = os.path.join(base_dir, "resources", "videos")
        os.makedirs(synth_dir, exist_ok=True)
        synth_path = os.path.join(synth_dir, "benchmark_synth.mp4")
        if not os.path.exists(synth_path):
            logger.info("Generating synthetic benchmark video...")
            generate_test_video(synth_path, scenario="normal", duration_sec=int(duration_sec + 5))
        cap = cv2.VideoCapture(synth_path)
        logger.info("Using synthetic benchmark stream: %s", synth_path)

    # Output CSV path
    if output_csv is None:
        logs_dir = os.path.join(base_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        output_csv = os.path.join(logs_dir, f"benchmark_{profile_name.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

    process = psutil.Process()
    logger.info("--- Starting AutoGuard DMS Benchmark [%s] for %.1fs ---", profile_name, duration_sec)

    records: List[Dict] = []
    latencies: List[float] = []
    fps_values: List[float] = []
    cpu_values: List[float] = []
    mem_values: List[float] = []

    start_bench = time.time()
    frame_idx = 0

    while (time.time() - start_bench) < duration_sec:
        frame_start = time.time()
        ret, frame = cap.read()
        if not ret or frame is None:
            if is_live:
                time.sleep(0.01)
                continue
            # Loop video if reached end
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
            if not ret or frame is None:
                break

        # Process frame through full CV & decision pipeline
        res = pipeline.process_frame(frame, source_name="Benchmark", source_type="video")
        t_proc = (time.time() - frame_start) * 1000.0
        frame_idx += 1

        # Sample resource usage every 10 frames
        cpu_pct = process.cpu_percent() if frame_idx % 10 == 0 else (cpu_values[-1] if cpu_values else 0.0)
        mem_pct = process.memory_percent()

        latencies.append(t_proc)
        fps_values.append(res.performance.fps)
        cpu_values.append(cpu_pct)
        mem_values.append(mem_pct)

        records.append({
            "frame_index": frame_idx,
            "elapsed_sec": round(time.time() - start_bench, 3),
            "latency_ms": round(t_proc, 2),
            "fps": res.performance.fps,
            "cpu_percent": round(cpu_pct, 1),
            "memory_percent": round(mem_pct, 1),
            "face_detected": res.face.detected,
            "gaze_direction": res.gaze.direction.value,
            "road_gaze_percent": res.distraction.road_gaze_percent,
            "distraction_state": res.distraction.state.value,
            "alert_level": res.alert.level.value
        })

    cap.release()
    total_elapsed = time.time() - start_bench

    # Summary calculations
    avg_fps = frame_idx / total_elapsed if total_elapsed > 0 else 0.0
    avg_latency = float(np.mean(latencies)) if latencies else 0.0
    p95_latency = float(np.percentile(latencies, 95)) if latencies else 0.0
    max_latency = float(np.max(latencies)) if latencies else 0.0
    avg_cpu = float(np.mean(cpu_values)) if cpu_values else 0.0
    avg_mem = float(np.mean(mem_values)) if mem_values else 0.0

    # Write CSV
    if records:
        fieldnames = list(records[0].keys())
        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)
        logger.info("Saved %d benchmark records to %s", len(records), output_csv)

    # Formatted Console Summary Table
    print("\n" + "=" * 62)
    print(f"      AUTOGUARD DMS BENCHMARK RESULTS — {profile_name.upper()}")
    print("      Architecture: Powered by cl0ud | Co-engineered by Ojas Singh")
    print("=" * 62)
    print(f" Total Elapsed Time:       {total_elapsed:.2f} s")
    print(f" Total Frames Processed:   {frame_idx} frames")
    print(f" Average Processing FPS:   {avg_fps:.1f} FPS")
    print(f" Mean Processing Latency:  {avg_latency:.1f} ms")
    print(f" 95th Percentile Latency:  {p95_latency:.1f} ms")
    print(f" Max Latency Spike:        {max_latency:.1f} ms")
    print(f" Mean Process CPU Load:    {avg_cpu:.1f} %")
    print(f" Mean Process Memory:      {avg_mem:.1f} %")
    print(f" Telemetry CSV Report:     {output_csv}")
    print("=" * 62 + "\n")

    return {
        "profile": profile_name,
        "elapsed_sec": total_elapsed,
        "frames": frame_idx,
        "avg_fps": avg_fps,
        "avg_latency_ms": avg_latency,
        "p95_latency_ms": p95_latency,
        "max_latency_ms": max_latency,
        "avg_cpu_percent": avg_cpu,
        "avg_mem_percent": avg_mem,
        "report_csv": output_csv
    }


def main():
    parser = argparse.ArgumentParser(description="AutoGuard DMS Performance Benchmark")
    parser.add_argument("--profile", type=str, default="BALANCED", choices=["LOW_POWER", "BALANCED", "HIGH_QUALITY", "MAC_DEVELOPMENT"], help="Power optimization profile")
    parser.add_argument("--duration", type=float, default=10.0, help="Benchmark run duration in seconds")
    parser.add_argument("--video", type=str, default=None, help="Optional prerecorded video path")
    parser.add_argument("--camera", type=int, default=0, help="Camera device index")
    parser.add_argument("--live", action="store_true", help="Benchmark physical live webcam instead of reproducible test video")
    parser.add_argument("--output", type=str, default=None, help="Output CSV path")

    args = parser.parse_args()
    run_benchmark(
        profile_name=args.profile,
        duration_sec=args.duration,
        video_path=args.video,
        camera_idx=args.camera,
        use_live_camera=args.live,
        output_csv=args.output
    )


if __name__ == "__main__":
    main()
