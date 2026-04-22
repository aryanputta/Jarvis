import os
import textwrap
import time

import cv2
import numpy as np

from app.utils.config import LOG_DIR, MEMORY_PANEL_ITEMS, MEMORY_PANEL_WIDTH

LOG_PATH = str(LOG_DIR / "commands.txt")


def smooth(prev, curr, alpha=0.6):
    if prev is None:
        return curr
    return int(alpha * curr + (1 - alpha) * prev)


class FPSCounter:
    def __init__(self, smoothing=10):
        self._times = []
        self._smoothing = smoothing

    def tick(self):
        now = time.time()
        self._times.append(now)
        if len(self._times) > self._smoothing:
            self._times.pop(0)
        if len(self._times) < 2:
            return 0.0
        elapsed = self._times[-1] - self._times[0]
        return (len(self._times) - 1) / elapsed if elapsed > 0 else 0.0


def clamp_coords(x, y, width, height):
    return max(0, min(x, width - 1)), max(0, min(y, height - 1))


def log_command(command: str):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {command}\n")


def draw_fps(frame, fps: float):
    cv2.putText(frame, f"FPS: {fps:.1f}", (10, frame.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    return frame


def _draw_wrapped_text(
    image: np.ndarray,
    text: str,
    x: int,
    y: int,
    width: int,
    color,
    prefix: str = "",
    line_height: int = 18,
) -> int:
    wrapped = textwrap.wrap(text, width=max(12, width))
    for line in wrapped:
        cv2.putText(
            image,
            f"{prefix}{line}",
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            color,
            1,
        )
        y += line_height
        prefix = "  " if prefix else ""
    return y


def draw_memory_panel(frame, panel):
    panel_width = min(MEMORY_PANEL_WIDTH, max(280, frame.shape[1] // 2))
    canvas = np.zeros((frame.shape[0], frame.shape[1] + panel_width, 3), dtype=np.uint8)
    canvas[:, :frame.shape[1]] = frame
    canvas[:, frame.shape[1]:] = (17, 20, 27)

    x = frame.shape[1] + 18
    y = 34

    cv2.putText(
        canvas,
        panel.get("header", "Jarvis Memory"),
        (x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.72,
        (255, 255, 255),
        2,
    )
    y += 22

    learning_label = "Learning On" if panel.get("learning_mode", True) else "Learning Off"
    cv2.putText(
        canvas,
        learning_label,
        (x, y + 12),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (151, 211, 179),
        1,
    )
    y += 34

    sections = [
        ("Recent Projects", panel.get("recent_projects") or ["No saved projects"]),
        ("Preferences Learned", panel.get("preferences") or ["No strong preferences saved"]),
        ("Continue Last Session", [panel.get("continue") or "No session to resume"]),
        ("Recent Agent Work", panel.get("recent_actions") or ["No agent actions saved"]),
        ("Saved Designs", panel.get("saved_designs") or ["No saved sketches"]),
        ("Latest Response", [panel.get("latest_response") or "Memory online"]),
    ]

    for title, items in sections:
        cv2.putText(
            canvas,
            title,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 209, 102),
            2,
        )
        y += 18
        for item in list(items)[:MEMORY_PANEL_ITEMS]:
            y = _draw_wrapped_text(canvas, str(item), x + 4, y + 18, 28, (235, 235, 235), prefix="- ")
        y += 12
        if y > frame.shape[0] - 80:
            break

    return canvas


def draw_status_banner(frame, text: str):
    if not text:
        return frame

    overlay = frame.copy()
    cv2.rectangle(overlay, (18, 18), (frame.shape[1] - 18, 78), (22, 26, 34), -1)
    frame = cv2.addWeighted(overlay, 0.82, frame, 0.18, 0)
    _draw_wrapped_text(frame, text, 32, 50, 72, (255, 255, 255))
    return frame
