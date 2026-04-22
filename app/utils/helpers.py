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
    canvas[:, frame.shape[1]:] = (15, 19, 26)

    x = frame.shape[1] + 18
    y = 34

    cv2.putText(
        canvas,
        "Jarvis",
        (x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.82,
        (255, 255, 255),
        2,
    )
    header_label = panel.get("header", "Personal Agent")
    cv2.putText(
        canvas,
        header_label,
        (x, y + 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (183, 190, 204),
        1,
    )
    y += 34

    learning_label = "Learning On" if panel.get("learning_mode", True) else "Learning Off"
    voice_label = (panel.get("voice_status") or "idle").replace("_", " ").title()
    cv2.putText(
        canvas,
        f"{learning_label}  |  {voice_label}",
        (x, y + 12),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (151, 211, 179),
        1,
    )
    y += 36

    sections = [
        ("Current Project", [panel.get("continue") or "No session loaded"]),
        ("Jarvis Heard", [panel.get("latest_heard") or "Waiting for speech input"]),
        ("Jarvis Said", [panel.get("latest_response") or "Ready when you are"]),
        ("Learned", panel.get("preferences") or ["No strong preferences saved yet"]),
        ("Recent Work", panel.get("recent_actions") or ["No agent actions yet"]),
        ("Saved Designs", panel.get("saved_designs") or ["No saved sketches"]),
    ]

    for title, items in sections:
        card_height = 82
        cv2.rectangle(canvas, (x - 10, y - 6), (x + panel_width - 38, y + card_height), (24, 29, 38), -1)
        cv2.rectangle(canvas, (x - 10, y - 6), (x + panel_width - 38, y + card_height), (44, 53, 68), 1)
        cv2.putText(
            canvas,
            title,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 209, 102),
            1,
        )
        y += 18
        for item in list(items)[:MEMORY_PANEL_ITEMS]:
            y = _draw_wrapped_text(canvas, str(item), x + 4, y + 18, 26, (235, 235, 235))
        y += 18
        if y > frame.shape[0] - 80:
            break

    return canvas


def draw_status_banner(frame, text: str):
    if not text:
        return frame

    overlay = frame.copy()
    x1, y1 = 18, 18
    x2, y2 = min(frame.shape[1] - 250, 560), 72
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (18, 22, 31), -1)
    frame = cv2.addWeighted(overlay, 0.82, frame, 0.18, 0)
    cv2.putText(frame, "Now", (34, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 209, 102), 1)
    _draw_wrapped_text(frame, text, 34, 62, 42, (255, 255, 255), line_height=16)
    return frame


def _voice_color(voice_status: str | None):
    voice_status = (voice_status or "").lower()
    if voice_status in {"mic_error", "speech_api_error"}:
        return (94, 94, 255)
    if voice_status in {"processing", "heard"}:
        return (86, 196, 255)
    if voice_status == "did_not_understand":
        return (102, 209, 255)
    return (151, 211, 179)


def _draw_voice_wave(frame, x: int, y: int, voice_status: str | None):
    voice_status = (voice_status or "idle").lower()
    base_levels = {
        "idle": [4, 8, 12, 8, 4],
        "listening": [10, 18, 26, 18, 10],
        "processing": [8, 22, 32, 22, 8],
        "heard": [12, 24, 18, 24, 12],
        "did_not_understand": [6, 14, 10, 14, 6],
        "speech_api_error": [3, 3, 3, 3, 3],
        "mic_error": [3, 3, 3, 3, 3],
    }
    levels = base_levels.get(voice_status, base_levels["idle"])
    pulse = int((time.time() * 6) % 8)
    color = _voice_color(voice_status)

    for index, base_height in enumerate(levels):
        animated_height = base_height
        if voice_status in {"listening", "processing", "heard"}:
            animated_height += (pulse + index * 2) % 8
        x1 = x + index * 14
        y1 = y - animated_height
        x2 = x1 + 8
        y2 = y
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, -1)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), 1)


def draw_agent_hud(
    frame,
    agent_status: str,
    voice_status: str | None,
    heard_text: str | None,
    response_text: str | None,
    project_name: str | None,
):
    card_width = min(400, max(320, frame.shape[1] // 3))
    card_height = 188
    x1 = frame.shape[1] - card_width - 28
    y1 = frame.shape[0] - card_height - 28
    x2 = frame.shape[1] - 28
    y2 = frame.shape[0] - 28

    overlay = frame.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (19, 24, 32), -1)
    frame = cv2.addWeighted(overlay, 0.88, frame, 0.12, 0)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 209, 102), 2)

    cv2.putText(frame, "Jarvis", (x1 + 16, y1 + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.76, (255, 255, 255), 2)
    cv2.putText(frame, agent_status.title(), (x1 + 16, y1 + 54), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (151, 211, 179), 1)
    cv2.putText(
        frame,
        (voice_status or "idle").replace("_", " ").title(),
        (x1 + 16, y1 + 76),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        _voice_color(voice_status),
        1,
    )
    _draw_voice_wave(frame, x2 - 94, y1 + 76, voice_status)
    if project_name:
        cv2.putText(
            frame,
            f"Project: {project_name[:28]}",
            (x1 + 16, y1 + 98),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (220, 220, 220),
            1,
        )

    y = y1 + 124
    cv2.putText(frame, "Heard", (x1 + 16, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 209, 102), 1)
    y = _draw_wrapped_text(frame, heard_text or "Waiting for speech input", x1 + 16, y + 16, 24, (245, 245, 245), line_height=16)
    y += 6
    cv2.putText(frame, "Reply", (x1 + 16, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 209, 102), 1)
    _draw_wrapped_text(frame, response_text or "Jarvis is online", x1 + 16, y + 16, 24, (245, 245, 245), line_height=16)
    return frame
