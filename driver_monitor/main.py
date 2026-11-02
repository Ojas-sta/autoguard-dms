"""
Main Application Entry Point for Driver Monitoring System (DMS).
Parses command-line arguments, selects active platform profile, and launches
either the native macOS GUI dashboard or headless verification pipeline.
"""

import argparse
import logging
import os
import sys
import time

# Ensure parent directory is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from driver_monitor.core.platform_manager import PlatformManager
from driver_monitor.models.download_models import ensure_model_downloaded
from driver_monitor.utils.audio_generator import ensure_alert_sounds
from driver_monitor.utils.video_generator import generate_all_test_videos

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("DMS")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AutoGuard Driver Drowsiness and Attention Monitoring System"
    )
    parser.add_argument(
        "--platform",
        type=str,
        choices=["macos", "raspberrypi"],
        default=None,
        help="Active platform profile (defaults to auto-detection)"
    )
    parser.add_argument(
        "--video",
        type=str,
        default=None,
        help="Optional path to a test video file (MP4, MOV, AVI) to play"
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=None,
        help="Camera device index (default: 0)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without GUI in headless benchmarking / test mode"
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=120,
        help="Number of frames to process in headless mode (default: 120)"
    )
    parser.add_argument(
        "--generate-assets",
        action="store_true",
        help="Pre-generate model, audio, and video assets then exit"
    )
    return parser.parse_args()


def run_headless(platform_mgr: PlatformManager, video_path: str, max_frames: int) -> None:
    """Runs detection pipeline in headless mode for benchmarking and CI testing."""
    from driver_monitor.camera.video_source import VideoSource
    from driver_monitor.core.detection_pipeline import DetectionPipeline
    from driver_monitor.hardware.hardware_factory import HardwareFactory

    logger.info("Starting Headless Verification Pipeline (Processing %d frames)...", max_frames)
    buzzer, leds, emergency_button = HardwareFactory.create_hardware(
        platform_mgr.active_platform, platform_mgr.config.hardware
    )
    pipeline = DetectionPipeline(platform_mgr.config, buzzer, leds, emergency_button)

    source = VideoSource(video_path, loop=True)
    if not source.open():
        logger.error("Failed to open video source: %s", video_path)
        sys.exit(1)

    latencies = []
    start_total = time.time()
    alert_counts = {}

    for i in range(max_frames):
        ret, frame = source.read_frame()
        if not ret:
            break
        res = pipeline.process_frame(frame, os.path.basename(video_path), "video")
        latencies.append(res.performance.processing_latency_ms)
        lvl = res.alert.level.value
        alert_counts[lvl] = alert_counts.get(lvl, 0) + 1

        if i % 30 == 0 or i == max_frames - 1:
            logger.info(
                "Frame %d/%d: Alert=%s, EAR=%.2f, MAR=%.2f, P=%.1f°, Latency=%.1fms",
                i + 1, max_frames, lvl, res.eyes.avg_ear, res.mouth.mar,
                res.head_pose.pitch, res.performance.processing_latency_ms
            )

    source.release()
    total_time = time.time() - start_total
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    effective_fps = len(latencies) / total_time if total_time > 0 else 0.0

    logger.info("=" * 60)
    logger.info("HEADLESS VERIFICATION SUMMARY")
    logger.info("Processed: %d frames in %.2f seconds", len(latencies), total_time)
    logger.info("Average Processing Latency: %.2f ms", avg_latency)
    logger.info("Effective Throughput: %.1f FPS", effective_fps)
    logger.info("Alert Level Distribution: %s", alert_counts)
    logger.info("Hardware Actuations Tested: Buzzer=%s, LEDs=%s", buzzer.is_active(), [leds.get_led(c) for c in ("green", "yellow", "orange", "red")])
    logger.info("=" * 60)


def main() -> None:
    args = parse_arguments()

    # 1. Platform Detection
    platform_mgr = PlatformManager(requested_platform=args.platform)
    logger.info("Active profile: %s (Detected: %s)", platform_mgr.active_platform, platform_mgr.get_info())

    if args.camera is not None:
        platform_mgr.config.camera.default_device_index = args.camera

    # 2. Asset Verification
    models_dir = os.path.join(BASE_DIR, "driver_monitor", "models")
    sounds_dir = os.path.join(BASE_DIR, "driver_monitor", "resources", "sounds")
    videos_dir = os.path.join(BASE_DIR, "driver_monitor", "resources", "videos")

    ensure_model_downloaded()
    ensure_alert_sounds(sounds_dir)
    test_videos = generate_all_test_videos(videos_dir)

    if args.generate_assets:
        logger.info("All model, audio, and video assets verified successfully.")
        return

    # 3. Headless Mode
    if args.headless:
        test_video = args.video or test_videos.get("eyes_closed") or list(test_videos.values())[0]
        run_headless(platform_mgr, test_video, args.frames)
        return

    # 4. Native Desktop GUI Launch
    try:
        from PyQt6.QtWidgets import QApplication
        from driver_monitor.dashboard.main_window import MainWindow

        app = QApplication(sys.argv)
        app.setApplicationName("AutoGuard Driver Monitoring System")
        app.setStyle("Fusion")

        window = MainWindow(platform_mgr, initial_video_path=args.video)
        window.show()

        sys.exit(app.exec())
    except ImportError as e:
        logger.error("PyQt6 not available: %s. Please install PyQt6 to launch GUI.", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
