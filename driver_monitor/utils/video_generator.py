"""
Procedural Test Video Generator for Driver Monitoring System.
Generates deterministic, standardized MP4 test videos for algorithm verification
and offline testing without requiring live driver webcam presence.
"""

import math
import os
import cv2
import numpy as np


def draw_synthetic_face(
    img: np.ndarray,
    cx: int = 320,
    cy: int = 240,
    eye_open: bool = True,
    eye_ratio: float = 1.0,
    mouth_open: bool = False,
    mouth_mar: float = 0.25,
    pitch_offset: int = 0,
    yaw_offset: int = 0,
    roll_deg: float = 0.0
) -> None:
    """Draws a synthetic human face with precise facial landmark geometry."""
    cx += yaw_offset
    cy += pitch_offset

    # Rotated face contour
    # Skin tone: (180, 205, 235) in BGR
    cv2.ellipse(img, (cx, cy), (125, 165), roll_deg, 0, 360, (180, 205, 235), -1)
    cv2.ellipse(img, (cx, cy), (125, 165), roll_deg, 0, 360, (140, 165, 200), 2)

    # Convert roll to radians for offset rotation
    rad = math.radians(roll_deg)
    cos_r = math.cos(rad)
    sin_r = math.sin(rad)

    def rot_pt(x, y):
        dx = x - cx
        dy = y - cy
        rx = cx + dx * cos_r - dy * sin_r
        ry = cy + dx * sin_r + dy * cos_r
        return int(rx), int(ry)

    # Eyebrows
    lb1 = rot_pt(cx - 75, cy - 65)
    lb2 = rot_pt(cx - 25, cy - 65)
    rb1 = rot_pt(cx + 25, cy - 65)
    rb2 = rot_pt(cx + 75, cy - 65)
    cv2.line(img, lb1, lb2, (50, 40, 30), 4)
    cv2.line(img, rb1, rb2, (50, 40, 30), 4)

    # Left eye
    leye_center = rot_pt(cx - 50, cy - 40)
    eye_h = max(2, int(15 * eye_ratio)) if eye_open else 2
    cv2.ellipse(img, leye_center, (24, eye_h), roll_deg, 0, 360, (255, 255, 255) if eye_open else (90, 80, 75), -1)
    cv2.ellipse(img, leye_center, (24, eye_h), roll_deg, 0, 360, (50, 40, 30), 1)
    if eye_open and eye_h > 4:
        cv2.circle(img, leye_center, 7, (70, 50, 30), -1)
        cv2.circle(img, (leye_center[0] - 2, leye_center[1] - 2), 2, (255, 255, 255), -1)

    # Right eye
    reye_center = rot_pt(cx + 50, cy - 40)
    cv2.ellipse(img, reye_center, (24, eye_h), roll_deg, 0, 360, (255, 255, 255) if eye_open else (90, 80, 75), -1)
    cv2.ellipse(img, reye_center, (24, eye_h), roll_deg, 0, 360, (50, 40, 30), 1)
    if eye_open and eye_h > 4:
        cv2.circle(img, reye_center, 7, (70, 50, 30), -1)
        cv2.circle(img, (reye_center[0] - 2, reye_center[1] - 2), 2, (255, 255, 255), -1)

    # Nose
    nose_top = rot_pt(cx, cy - 10)
    nose_bot = rot_pt(cx, cy + 22)
    cv2.line(img, nose_top, nose_bot, (140, 160, 195), 3)

    # Mouth
    mouth_center = rot_pt(cx, cy + 72)
    mouth_h = max(8, int(50 * mouth_mar)) if mouth_open else max(6, int(18 * mouth_mar))
    mouth_col = (40, 20, 80) if mouth_open else (90, 80, 180)
    cv2.ellipse(img, mouth_center, (35, mouth_h), roll_deg, 0, 360, mouth_col, -1)
    cv2.ellipse(img, mouth_center, (35, mouth_h), roll_deg, 0, 360, (70, 60, 140), 2)


def generate_test_video(
    output_path: str,
    scenario: str = "normal",
    duration_sec: float = 6.0,
    fps: int = 30,
    width: int = 640,
    height: int = 480
) -> str:
    """Generates an MP4 video for a specific driver behavior scenario."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    total_frames = int(duration_sec * fps)

    for i in range(total_frames):
        t = i / float(fps)
        img = np.full((height, width, 3), 35, dtype=np.uint8)

        # Subtle dark interior cockpit vignette
        cv2.circle(img, (width // 2, height // 2), 340, (45, 45, 50), -1)

        eye_open = True
        eye_ratio = 1.0
        mouth_open = False
        mouth_mar = 0.25
        pitch = 0
        yaw = 0
        roll = 0.0
        face_present = True

        if scenario == "normal":
            # Normal periodic natural blinks (every 2.5s for 0.15s)
            cycle = t % 2.5
            if cycle < 0.15:
                eye_open = False
                eye_ratio = 0.1
            else:
                eye_open = True
                eye_ratio = 1.0
            # Gentle breathing head sway
            pitch = int(3 * math.sin(2 * math.pi * 0.4 * t))

        elif scenario == "eyes_closed":
            # Open for first 1.2s, then closed for rest of video
            if t < 1.2:
                eye_open = True
                eye_ratio = 1.0
            else:
                eye_open = False
                eye_ratio = 0.1

        elif scenario == "head_nodding":
            # 3 distinct downward nod cycles
            # Nod every 1.8s
            nod_cycle = t % 1.8
            if nod_cycle < 0.8:
                # Dropping down
                pitch = int(35 * math.sin(math.pi * nod_cycle / 0.8))
                eye_ratio = max(0.2, 1.0 - (pitch / 40.0))
            else:
                pitch = 0
                eye_ratio = 1.0

        elif scenario == "yawning":
            # Normal for 1.0s, then sustained yawn for 3.0s
            if 1.0 <= t <= 4.0:
                mouth_open = True
                mouth_mar = 0.65
                eye_ratio = 0.5  # Eyes squint during yawn
            else:
                mouth_open = False
                mouth_mar = 0.25

        elif scenario == "head_tilted":
            # Normal for 1s, then sustained sideways roll (35 degrees)
            if t >= 1.0:
                roll = 35.0
            else:
                roll = 0.0

        elif scenario == "head_turned":
            # Normal for 1s, then turned far right (yaw offset)
            if t >= 1.0:
                yaw = 110
            else:
                yaw = 0

        elif scenario == "face_lost":
            # Present for first 1.2s, then moves completely off camera
            if t >= 1.2:
                face_present = False

        if face_present:
            draw_synthetic_face(
                img,
                cx=width // 2,
                cy=height // 2,
                eye_open=eye_open,
                eye_ratio=eye_ratio,
                mouth_open=mouth_open,
                mouth_mar=mouth_mar,
                pitch_offset=pitch,
                yaw_offset=yaw,
                roll_deg=roll
            )

        # Frame counter & scenario watermark
        cv2.putText(
            img,
            f"SCENARIO: {scenario.upper()} | T: {t:.2f}s",
            (15, height - 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (180, 180, 180),
            1,
            cv2.LINE_AA
        )

        out.write(img)

    out.release()
    return output_path


def generate_all_test_videos(output_dir: str) -> dict[str, str]:
    """Generates the full suite of standardized test videos."""
    os.makedirs(output_dir, exist_ok=True)
    scenarios = [
        ("test_normal.mp4", "normal", 6.0),
        ("test_eyes_closed.mp4", "eyes_closed", 6.0),
        ("test_head_nodding.mp4", "head_nodding", 6.0),
        ("test_yawning.mp4", "yawning", 6.0),
        ("test_head_tilted.mp4", "head_tilted", 6.0),
        ("test_head_turned.mp4", "head_turned", 6.0),
        ("test_face_lost.mp4", "face_lost", 6.0),
    ]

    paths = {}
    for filename, scenario, duration in scenarios:
        path = os.path.join(output_dir, filename)
        if not os.path.exists(path):
            generate_test_video(path, scenario=scenario, duration_sec=duration)
        paths[scenario] = path

    return paths


if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    videos_dir = os.path.join(os.path.dirname(current_dir), "resources", "videos")
    generated = generate_all_test_videos(videos_dir)
    print("Generated test videos:", generated)
