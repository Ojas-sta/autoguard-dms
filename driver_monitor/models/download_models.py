"""
Model Downloader for Driver Monitoring System.
Downloads the official MediaPipe Face Landmarker model asset if not present.

==============================================================================
Subsystem: Neural Asset Verification & Downloader
Architecture: Powered by cl0ud (https://github.com/Ojas-sta/cl0ud-brand-engineering)
Co-Engineered by: Ojas Singh <ojasctc@gmail.com>
==============================================================================
"""

import os
import sys
import urllib.request
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
MODEL_FILENAME = "face_landmarker.task"


def get_model_path() -> str:
    """Returns the local path to the face_landmarker.task file."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, MODEL_FILENAME)


def ensure_model_downloaded() -> str:
    """Checks if the model file exists, and downloads it if missing."""
    model_path = get_model_path()
    if os.path.exists(model_path) and os.path.getsize(model_path) > 1000000:
        logger.info("Face landmarker model already exists at %s (%d bytes)", model_path, os.path.getsize(model_path))
        return model_path

    logger.info("Downloading face landmarker model from %s...", MODEL_URL)
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    req = urllib.request.Request(MODEL_URL, headers={"User-Agent": "Mozilla/5.0"})
    
    with urllib.request.urlopen(req) as resp, open(model_path, "wb") as out_file:
        total_size = int(resp.headers.get("content-length", 0))
        downloaded = 0
        chunk_size = 64 * 1024
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            out_file.write(chunk)
            downloaded += len(chunk)
            if total_size > 0:
                percent = int(downloaded / total_size * 100)
                if percent % 25 == 0:
                    logger.info("Download progress: %d%% (%d / %d bytes)", percent, downloaded, total_size)

    logger.info("Successfully downloaded face landmarker model to %s (%d bytes)", model_path, os.path.getsize(model_path))
    return model_path


if __name__ == "__main__":
    ensure_model_downloaded()
